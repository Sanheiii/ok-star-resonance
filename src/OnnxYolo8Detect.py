from typing import override

import onnxruntime as ort

from ok import Logger, sort_boxes, og
from src.Yolo8Detect import Yolo8Detect

logger = Logger.get_logger(__name__)


class OnnxYolo8Detect(Yolo8Detect):

    def __init__(self, weights='bpsr_splash.onnx', labels=None, model_h=640, model_w=640, iou_thres=0.45):
        """
        YOLOv8 ONNX Runtime inference
        """
        self.session = None
        self.input_name = None
        self.output_name = None
        self.model_actual_input_h = None
        self.model_actual_input_w = None
        super().__init__(weights, labels, model_h, model_w, iou_thres)

    @override
    def initialize(self):
        options = ort.SessionOptions()

        available_providers = ort.get_available_providers()
        logger.info(f"Available ONNX Runtime providers: {available_providers}")

        # Prioritize DirectML, then CUDA, then CPU
        providers = []
        if og.use_dml and 'DmlExecutionProvider' in available_providers:
            logger.info("Attempting to use DirectML Execution Provider.")
            providers.append(('DmlExecutionProvider', {'device_id': 0}))
        elif 'CUDAExecutionProvider' in available_providers:
            logger.info("Attempting to use CUDA Execution Provider.")
            providers.append(('CUDAExecutionProvider', {'device_id': 0}))

        providers.append('CPUExecutionProvider')  # Always include CPU as a fallback

        try:
            logger.info(f"Initializing ONNX Runtime session with providers: {providers} for model: {self.weights}")
            self.session = ort.InferenceSession(self.weights, sess_options=options, providers=providers)

            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name

            model_input_shape = self.session.get_inputs()[0].shape  # e.g., [1, 3, 640, 640] for NCHW
            self.model_actual_input_h = model_input_shape[2]
            self.model_actual_input_w = model_input_shape[3]

            if self.model_h != self.model_actual_input_h or \
                    self.model_w != self.model_actual_input_w:
                logger.warning(
                    f"User-specified preprocessing HxW ({self.model_h}x{self.model_w}) "
                    f"differs from ONNX model's expected input HxW ({self.model_actual_input_h}x{self.model_actual_input_w}). "
                    f"Using user-specified dimensions ({self.model_h}x{self.model_w}) for preprocessing. "
                    "Ensure this is intended and the model supports dynamic input sizes or this specific size."
                )

            active_provider = self.session.get_providers()[0]
            logger.info(f"ONNX Runtime active provider: {active_provider}")
            logger.info(f"ONNX Runtime model loaded successfully using {self.session.get_providers()}.")
            logger.info(f"Model Input: '{self.input_name}' with shape {model_input_shape}")
            logger.info(f"Model Output: '{self.output_name}' with shape {self.session.get_outputs()[0].shape}")

        except Exception as e:
            logger.error(f"Error initializing ONNX Runtime session: {e}")
            raise RuntimeError("Could not initialize ONNX Runtime model") from e

    @override
    def detect(self, image, threshold=0.5, label=-1):
        try:
            h, w = image.shape[:2]
            img_data, pad = self._preprocess(image)
            outputs = self.session.run([self.output_name], {self.input_name: img_data})
            boxes = self._postprocess(outputs[0], pad, (h, w), threshold, label)
            return sort_boxes(boxes)
        except Exception as e:
            logger.error(f'ONNX Runtime yolo detect error: {e}')
            return []