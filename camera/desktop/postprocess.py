import numpy as np


CLASSES = ("aeroplane", "bicycle", "bird", "boat", "bottle", "bus", "car", "cat",
           "chair", "cow", "diningtable", "dog", "horse", "motorbike", "person",
           "pottedplant", "sheep", "sofa", "train", "tvmonitor")
CLASS_LABELS = ("飞机", "自行车", "鸟", "船", "瓶子", "公交车", "汽车", "猫", "椅子", "牛",
                "餐桌", "狗", "马", "摩托车", "人", "盆栽", "羊", "沙发", "火车", "显示器")
# Grid-unit anchors from the author's Update-2023-11-08/vitis_postprocess/src/nms.cpp.
ANCHORS = (((2.5312, 2.5625), (4.2188, 5.2812), (10.75, 9.9688)),
           ((1.4375, 1.6875), (2.3125, 3.625), (5.0625, 5.125)))


def sigmoid(values):
    return np.exp(-np.logaddexp(0, -values))


def decode(raw, size, anchors, confidence):
    prediction = np.frombuffer(raw, dtype="<i2").astype(np.float64).reshape(3, 25, size, size) / 512
    prediction = prediction.transpose(0, 2, 3, 1)
    class_id = prediction[..., 5:].argmax(axis=-1)
    best = np.take_along_axis(prediction[..., 5:], class_id[..., None], axis=-1)[..., 0]
    score = sigmoid(prediction[..., 4]) * sigmoid(best)
    mask = score >= confidence
    anchor, row, column = np.nonzero(mask)
    selected = prediction[mask]
    center = (sigmoid(selected[:, :2]) + np.column_stack((column, row))) * (416 / size)
    dimensions = np.exp(selected[:, 2:4]) * np.asarray(anchors)[anchor] * (416 / size)
    boxes = np.column_stack((center - dimensions / 2, center + dimensions / 2))
    return boxes, score[mask], class_id[mask]


def nms(boxes, scores, classes, threshold):
    keep = []
    for class_id in np.unique(classes):
        indices = np.flatnonzero(classes == class_id)
        indices = indices[np.argsort(-scores[indices], kind="stable")]
        while indices.size:
            current = indices[0]
            keep.append(int(current))
            others = indices[1:]
            if not others.size:
                break
            lower = np.maximum(boxes[current, :2], boxes[others, :2])
            upper = np.minimum(boxes[current, 2:], boxes[others, 2:])
            intersection = np.maximum(upper - lower, 0).prod(axis=1)
            area = np.maximum(boxes[:, 2:] - boxes[:, :2], 0).prod(axis=1)
            union = area[current] + area[others] - intersection
            overlap = np.divide(intersection, union, out=np.zeros_like(union, dtype=np.float64), where=union > 0)
            indices = others[overlap <= threshold]
    return sorted(keep, key=lambda index: -scores[index])


def detect(out0, out1, confidence=0.5, iou=0.3):
    heads = [decode(raw, size, anchors, confidence)
             for raw, size, anchors in zip((out0, out1), (13, 26), ANCHORS)]
    boxes, scores, classes = (np.concatenate([head[i] for head in heads]) for i in range(3))
    return [{"class_id": int(classes[index]), "class_name": CLASSES[classes[index]],
             "score": float(scores[index]), "box": boxes[index].clip(0, 416).tolist()}
            for index in nms(boxes, scores, classes, iou)]
