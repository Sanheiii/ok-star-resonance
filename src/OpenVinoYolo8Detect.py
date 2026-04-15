from typing import override

from openvino import Core

from ok import Logger, sort_boxes
from src.Yolo8Detect import Yolo8Detect

logger = Logger.get_logger(__name__)


class OpenVinoYolo8Detect(Yolo8Detect):

    def __init__(self, weights='bpsr_splash.onnx', labels=None, model_h=640, model_w=640, iou_thres=0.45):
        """
        YOLOv8 OpenVINO inference
        """
        self.core = None
        self.compiled_model = None
        self.input_layer = None
        self.output_layer = None
        super().__init__(weights, labels, model_h, model_w, iou_thres)

    @override
    def initialize(self):
        self.core = Core()
        device = "CPU"

        try:
            logger.info(f"Compiling OpenVINO model for {device}...")
            model = self.core.read_model(model=self.weights)
            self.compiled_model = self.core.compile_model(model=model, device_name=device,
                                                          config={"PERFORMANCE_HINT": "LATENCY"})
            self.input_layer = self.compiled_model.input(0)
            self.output_layer = self.compiled_model.output(0)
            self.target_h = self.input_layer.shape[2]
            self.target_w = self.input_layer.shape[3]
            logger.info(f"OpenVINO model compiled successfully for {device}. {self.target_w}x{self.target_h}.")
        except Exception as e:
            logger.error(f"Error initializing OpenVINO: {e}")
            raise RuntimeError("Could not initialize OpenVINO model") from e

    @override
    def detect(self, image, threshold=0.5, label=-1):
        try:
            h, w = image.shape[:2]
            img_data, pad = self._preprocess(image)
            results = self.compiled_model({self.input_layer: img_data})
            outputs = results[self.output_layer]
            boxes = self._postprocess(outputs, pad, (h, w), threshold, label)
            return sort_boxes(boxes)
        except Exception as e:
            logger.error(f'OpenVINO yolo detect error: {e}')
            return []