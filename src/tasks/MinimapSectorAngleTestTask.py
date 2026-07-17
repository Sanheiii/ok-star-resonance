import time

from src.MinimapSectorAngleDetector import MinimapSectorAngleDetector
from src.tasks.SRTask import SRTask


class MinimapSectorAngleTestTask(SRTask):
    """Continuously report translucent minimap-sector detection metrics."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Minimap Sector Angle Test"
        self.description = "Continuously estimates the translucent sector angle on the minimap."

    def run(self):
        while True:
            self.next_frame()
            detection_started_at = time.perf_counter()
            result = MinimapSectorAngleDetector.detect(self.frame)
            if result is None:
                self.info["Sector Angle"] = "Not detected"
                self.info["Confidence"] = "0.00"
                self.info["Detection Status"] = "No complete bright/dark sector edge pair was found."
                for key in self._metric_info_keys():
                    self.info[key] = "-"
            else:
                angle, confidence, metrics = result
                self.info["Sector Angle"] = f"{angle:.1f}°"
                self.info["Confidence"] = f"{confidence:.2f}"
                self.info["Detection Status"] = "Detected"
                self.info["Bright Edge Angle"] = f"{metrics['bright_edge_angle']:.1f}°"
                self.info["Dark Edge Angle"] = f"{metrics['dark_edge_angle']:.1f}°"
                self.info["Bright Edge Coverage"] = f"{metrics['bright_edge_coverage']:.1%}"
                self.info["Dark Edge Coverage"] = f"{metrics['dark_edge_coverage']:.1%}"
                self.info["Paired Edge Strength"] = f"{metrics['paired_edge_strength']:.6f}"
                self.info["Center Whiteness"] = f"{metrics['center_whiteness']:.4f}"
                self.info["Inside Outside Whiteness"] = f"{metrics['inside_outside_whiteness']:.4f}"
                self.info["Weighted Score"] = f"{metrics['weighted_score']:.3f}"
                self.info["Candidate Count"] = metrics["candidate_count"]
                self.info["Probe Points"] = metrics["probe_points"]
            detection_time_ms = (time.perf_counter() - detection_started_at) * 1000.0
            self.info["Detection Time"] = f"{detection_time_ms:.2f} ms"
            self.sleep(0.05)

    @staticmethod
    def _metric_info_keys():
        return (
            "Bright Edge Angle",
            "Dark Edge Angle",
            "Bright Edge Coverage",
            "Dark Edge Coverage",
            "Paired Edge Strength",
            "Center Whiteness",
            "Inside Outside Whiteness",
            "Weighted Score",
            "Candidate Count",
            "Probe Points",
        )
