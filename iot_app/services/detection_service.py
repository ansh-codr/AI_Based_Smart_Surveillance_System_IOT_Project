import cv2


class DetectionService:
    def __init__(self, config):
        self.config = config
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect_people(self, frame):
        small = cv2.resize(frame, (self.config.detect_width, self.config.detect_height))
        boxes, _weights = self.hog.detectMultiScale(
            small,
            winStride=(8, 8),
            padding=(8, 8),
            scale=1.08,
        )
        return boxes

    def draw_person_boxes(self, frame, boxes):
        scale_x = frame.shape[1] / float(self.config.detect_width)
        scale_y = frame.shape[0] / float(self.config.detect_height)
        for x, y, w, h in boxes:
            x1 = int(x * scale_x)
            y1 = int(y * scale_y)
            x2 = int((x + w) * scale_x)
            y2 = int((y + h) * scale_y)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
