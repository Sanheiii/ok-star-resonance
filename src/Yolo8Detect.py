import numpy as np
import cv2
from typing import Tuple

from ok import Box


class Yolo8Detect:
    def __init__(self, weights='bpsr_splash.onnx', labels=None, model_h=640, model_w=640, iou_threshold=0.45):
        if labels is None:
            labels = {0: 'splash'}
        self.dic_labels = labels
        self.weights = weights
        self.model_w = model_w
        self.model_h = model_h
        self.iou_threshold = iou_threshold
        self.target_h = model_h
        self.target_w = model_w
        self.initialize()

    def initialize(self):
        pass

    def _preprocess(self, img):
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img, pad = self.letterbox(img, (self.target_h, self.target_w))
        image_data = np.array(img) / 255.0
        image_data = np.transpose(image_data, (2, 0, 1))
        image_data = np.expand_dims(image_data, axis=0).astype(np.float32)
        return image_data, pad

    def _postprocess(self, output, padding, orig_shape, confidence_threshold, label):
        processed_outputs = np.transpose(np.squeeze(output))
        rows = processed_outputs.shape[0]

        boxes = []
        scores = []
        class_ids = []

        gain = min(self.target_h / orig_shape[0], self.target_w / orig_shape[1])

        processed_outputs[:, 0] -= padding[1]
        processed_outputs[:, 1] -= padding[0]

        for i in range(rows):
            classes_scores = processed_outputs[i][4:]
            max_score = np.amax(classes_scores)
            class_id = np.argmax(classes_scores)

            if max_score >= confidence_threshold and (label == -1 or label == class_id):
                x, y, w, h = processed_outputs[i][0], processed_outputs[i][1], \
                    processed_outputs[i][2], processed_outputs[i][3]

                left = int((x - w / 2) / gain)
                top = int((y - h / 2) / gain)
                width = int(w / gain)
                height = int(h / gain)

                class_ids.append(class_id)
                scores.append(max_score)
                boxes.append([left, top, width, height])

        indices = cv2.dnn.NMSBoxes(boxes, scores, confidence_threshold, self.iou_threshold)

        results = []
        for i in indices:
            box = boxes[i]
            box_obj = Box(box[0], box[1], box[2], box[3])
            box_obj.name = self.dic_labels.get(int(class_ids[i]), 'unknown')
            box_obj.confidence = scores[i]
            results.append(box_obj)
        return results

    def detect(self, image, threshold=0.5, label=-1):
        pass

    @staticmethod
    def letterbox(img: np.ndarray, new_shape: Tuple[int, int] = (640, 640)) -> Tuple[np.ndarray, Tuple[int, int]]:
        """
        Resize and reshape images while maintaining aspect ratio by adding padding.

        Args:
            img (np.ndarray): Input image to be resized.
            new_shape (Tuple[int, int]): Target shape (height, width) for the image.

        Returns:
            (np.ndarray): Resized and padded image.
            (Tuple[int, int]): Padding values (top, left) applied to the image.
        """
        shape = img.shape[:2]  # current shape [height, width]

        # Scale ratio (new / old)
        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])

        # Compute padding
        new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
        dw, dh = (new_shape[1] - new_unpad[0]) / 2, (new_shape[0] - new_unpad[1]) / 2  # wh padding

        if shape[::-1] != new_unpad:  # resize
            img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))

        return img, (top, left)