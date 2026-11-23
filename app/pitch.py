"""Validated normalized-image to metric-pitch mapping."""
import cv2
import numpy as np


class LandmarkDetector:
    """Adapter for YOLO pose weights with an explicit, matching landmark layout."""
    def __init__(self, model_path, layout):
        from ultralytics import YOLO
        self.model = YOLO(str(model_path))
        if self.model.task != "pose":
            raise ValueError("Pitch model must be a pose/keypoint model")
        self.points = np.asarray(layout["points"], dtype=float)
        self.length, self.width = float(layout["length"]), float(layout["width"])
        if self.points.ndim != 2 or self.points.shape[1] != 2 or len(self.points) < 4:
            raise ValueError("Layout requires ordered metric landmark points")
        if not np.isfinite(self.points).all() or not (self.length > 0 and self.width > 0):
            raise ValueError("Invalid metric pitch dimensions")

    def detect(self, image):
        result = self.model(image, imgsz=1280, conf=.3, verbose=False)[0]
        points = result.keypoints
        if points is None or not len(points) or points.conf is None:
            return []
        xy, confidence = points.xyn[0].cpu().numpy(), points.conf[0].cpu().numpy()
        if len(xy) != len(self.points):
            raise ValueError("Model landmark count does not match layout")
        return [dict(image=p.tolist(), pitch=metric.tolist(), confidence=float(c))
                for p, metric, c in zip(xy, self.points, confidence)
                if c >= .7 and np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()]


def fit_pitch(image_points, pitch_points):
    source, target = np.asarray(image_points, dtype=float), np.asarray(pitch_points, dtype=float)
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 2 or len(source) < 4:
        return None
    if not np.isfinite(source).all() or not np.isfinite(target).all():
        return None
    if np.linalg.matrix_rank(source - source.mean(axis=0)) < 2:
        return None
    matrix, inliers = cv2.findHomography(source, target, cv2.RANSAC, 1.5)
    if matrix is None or inliers is None or inliers.sum() < 4 or not np.isfinite(matrix).all():
        return None
    if np.linalg.cond(matrix) > 1e8:
        return None
    projected = cv2.perspectiveTransform(source[None], matrix)[0]
    error = np.linalg.norm(projected - target, axis=1)[inliers.ravel().astype(bool)]
    if np.median(error) > 1.0:
        return None
    return dict(matrix=matrix.tolist(), median_error_m=float(np.median(error)),
                inliers=int(inliers.sum()), correspondences=len(source))


def project(position, matrix):
    point = np.asarray(matrix) @ np.array([*position, 1.])
    if not np.isfinite(point).all() or abs(point[2]) < 1e-8:
        return None
    return (point[:2] / point[2]).tolist()


def map_frames(frames, length=105., width=68.):
    valid = 0
    for frame in frames:
        landmarks = frame.get("landmarks", [])
        fit = fit_pitch([p["image"] for p in landmarks], [p["pitch"] for p in landmarks]) if landmarks else None
        frame["calibration"] = fit
        valid += bool(fit)
        for player in frame["players"]:
            point = project(player["position"], fit["matrix"]) if fit else None
            player["pitch"] = point if point and 0 <= point[0] <= length and 0 <= point[1] <= width else None
    return valid
