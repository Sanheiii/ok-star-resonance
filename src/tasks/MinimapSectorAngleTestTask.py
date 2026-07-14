import time

import cv2
import numpy as np

from src.tasks.SRTask import SRTask


class SectorNotDetectedError(RuntimeError):
    pass


class MinimapSectorAngleTestTask(SRTask):
    """Estimate the direction of a translucent white sector on the minimap."""

    # TODO: Fill in (left, top, right, bottom) using 0-1 screen coordinates.
    MINIMAP_REGION = (71/2560,47/1440, 295/2560, 271/1440)

    _ANGLE_BINS = 360
    # Use a centered circle whose diameter is half of the configured region.
    _DETECTION_RADIUS_RATIO = 0.50
    _CENTER_EXCLUSION_RADIUS_AT_1440P = 15.0
    _OUTER_RADIUS_RATIO = 1
    # Compare one radial line with the preceding radial line. The probe has no
    # angular thickness; inner/outer radii only control its start and end.
    _EDGE_SAMPLE_WIDTH_DEGREES = 1
    _MIN_EDGE_POINT_CONSISTENCY = 0.75
    _MIN_PAIRED_EDGE_SCORE = 2e-4
    _CENTER_WHITENESS_WEIGHT = 0.35
    _INSIDE_OUTSIDE_WHITENESS_WEIGHT = 0.65

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Minimap Sector Angle Test"
        self.description = "Continuously estimates the translucent sector angle on the minimap."

    def run(self):
        if self.MINIMAP_REGION is None:
            self.info["Sector Angle"] = "Set MINIMAP_REGION first"
            return

        region = self.box_of_screen(*self.MINIMAP_REGION)
        while True:
            self.next_frame()
            minimap = region.crop_frame(self.frame)
            center_exclusion_radius = (
                self._CENTER_EXCLUSION_RADIUS_AT_1440P
                * self.frame.shape[0]
                / 1440.0
            )
            detection_started_at = time.perf_counter()
            try:
                angle, confidence, metrics = self._estimate_sector_angle(
                    minimap,
                    92,
                    center_exclusion_radius,
                )
            except SectorNotDetectedError as error:
                self.info["Sector Angle"] = "Not detected"
                self.info["Confidence"] = "0.00"
                self.info["Detection Status"] = str(error)
                for key in self._metric_info_keys():
                    self.info[key] = "-"
            else:
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
            detection_time_ms = (
                time.perf_counter() - detection_started_at
            ) * 1000.0
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

    @classmethod
    def _estimate_sector_angle(
        cls,
        image,
        sector_width_degrees,
        center_exclusion_radius=0.0,
    ):
        if image is None or image.size == 0:
            raise ValueError("Minimap region is empty.")

        height, width = image.shape[:2]
        center_x = (width - 1) / 2.0
        center_y = (height - 1) / 2.0
        region_radius = min(width, height) / 2.0
        detection_radius = region_radius * cls._DETECTION_RADIUS_RATIO

        normalized_color = image.astype(np.float32) / 255.0
        # A genuinely white overlay raises every color channel. Using the
        # darkest channel suppresses saturated blue/purple UI markers.
        whiteness = np.min(normalized_color, axis=2)

        inner_radius = center_exclusion_radius
        outer_radius = detection_radius * cls._OUTER_RADIUS_RATIO
        if inner_radius >= outer_radius:
            raise ValueError("The minimap region is too small for the sampling ring.")

        polar_whiteness = cls._sample_polar_ring(
            whiteness,
            center_x,
            center_y,
            inner_radius,
            outer_radius,
        )
        # Median aggregation prevents a bright object at only a few radii from
        # dominating the complete angular profile.
        angle_score = np.median(polar_whiteness, axis=0)
        angle_score = cls._circular_smooth(angle_score, 7)

        window_size = max(
            1,
            round(cls._ANGLE_BINS * sector_width_degrees / 360.0),
        )
        window_score = cls._circular_window_mean(angle_score, window_size)

        # A white translucent sector produces a positive edge where it starts
        # and a negative edge where it ends. Pair those two transitions using
        # the configured sector width so bright map areas alone score poorly.
        edge_width = max(
            1,
            round(
                cls._ANGLE_BINS
                * cls._EDGE_SAMPLE_WIDTH_DEGREES
                / 360.0
            ),
        )
        sector_end_indices = (
            np.arange(cls._ANGLE_BINS) + window_size
        ) % cls._ANGLE_BINS
        radial_whiteness_edge = cls._circular_edge_response(
            polar_whiteness,
            edge_width,
            axis=1,
        )
        # Consistency describes whether almost every point on the radial probe
        # becomes whiter/darker.
        enter_consistency = np.mean(radial_whiteness_edge > 0.0, axis=0)
        leave_consistency = np.mean(radial_whiteness_edge < 0.0, axis=0)
        # A real sector boundary crosses most sampled radii at the same angle;
        # terrain edges usually affect only a subset of them.
        enter_edge_score = np.median(radial_whiteness_edge, axis=0)
        leave_edge_score = np.median(-radial_whiteness_edge, axis=0)
        # Both edges are mandatory. A geometric mean prevents one very strong
        # terrain edge from compensating for a missing opposite edge.
        paired_edge_score = np.sqrt(
            np.maximum(enter_edge_score, 0.0)
            * np.maximum(leave_edge_score[sector_end_indices], 0.0)
        )

        # Rotate the probe clockwise. Whenever a line becomes brighter, check
        # whether the line one sector-width later becomes darker, and store the
        # complete edge pair. Edge strength is only an admission condition.
        edge_pairs = []
        for start_index in range(cls._ANGLE_BINS):
            end_index = int(sector_end_indices[start_index])
            if (
                enter_consistency[start_index]
                >= cls._MIN_EDGE_POINT_CONSISTENCY
                and leave_consistency[end_index]
                >= cls._MIN_EDGE_POINT_CONSISTENCY
                and paired_edge_score[start_index]
                >= cls._MIN_PAIRED_EDGE_SCORE
            ):
                edge_pairs.append((start_index, end_index))
        if not edge_pairs:
            raise SectorNotDetectedError(
                "No complete bright/dark sector edge pair was found."
            )
        candidate_indices = np.array(
            [start_index for start_index, _ in edge_pairs],
            dtype=np.int32,
        )

        # Stage 2: inside a translucent white sector, the part nearer the
        # center is whiter because opacity decreases towards the outer edge.
        radial_band_size = max(1, polar_whiteness.shape[0] // 3)
        inner_whiteness = np.median(
            polar_whiteness[:radial_band_size],
            axis=0,
        )
        outer_whiteness = np.median(
            polar_whiteness[-radial_band_size:],
            axis=0,
        )
        center_whiteness_score = cls._circular_window_mean(
            inner_whiteness - outer_whiteness,
            window_size,
        )
        # Compare the sector interior with the angles outside the sector.
        if window_size < cls._ANGLE_BINS:
            outside_score = (
                np.sum(angle_score) - window_score * window_size
            ) / (cls._ANGLE_BINS - window_size)
            inside_outside_score = window_score - outside_score
        else:
            inside_outside_score = window_score

        # Edges only decide which pairs are eligible. Rank those pairs using
        # the two whiteness characteristics requested by the minimap mask.
        normalized_center_score = cls._normalize_candidates(
            center_whiteness_score,
            candidate_indices,
        )
        normalized_inside_outside_score = cls._normalize_candidates(
            inside_outside_score,
            candidate_indices,
        )
        final_score = np.full(cls._ANGLE_BINS, -np.inf, dtype=np.float32)
        final_score[candidate_indices] = (
            cls._CENTER_WHITENESS_WEIGHT
            * normalized_center_score[candidate_indices]
            + cls._INSIDE_OUTSIDE_WHITENESS_WEIGHT
            * normalized_inside_outside_score[candidate_indices]
        )

        sector_start = int(np.argmax(final_score))
        sector_center = (sector_start + window_size / 2.0) % cls._ANGLE_BINS
        angle = sector_center * 360.0 / cls._ANGLE_BINS
        confidence = (
            float(paired_edge_score[sector_start])
            / (float(np.max(paired_edge_score)) + 1e-6)
        )
        sector_end = int(sector_end_indices[sector_start])
        metrics = {
            "bright_edge_angle": sector_start * 360.0 / cls._ANGLE_BINS,
            "dark_edge_angle": sector_end * 360.0 / cls._ANGLE_BINS,
            "bright_edge_coverage": float(enter_consistency[sector_start]),
            "dark_edge_coverage": float(leave_consistency[sector_end]),
            "paired_edge_strength": float(paired_edge_score[sector_start]),
            "center_whiteness": float(center_whiteness_score[sector_start]),
            "inside_outside_whiteness": float(inside_outside_score[sector_start]),
            "weighted_score": float(final_score[sector_start]),
            "candidate_count": len(edge_pairs),
            "probe_points": int(polar_whiteness.shape[0]),
        }
        return angle, confidence, metrics

    @classmethod
    def _sample_polar_ring(
        cls,
        image,
        center_x,
        center_y,
        inner_radius,
        outer_radius,
    ):
        radial_samples = max(2, int(np.ceil(outer_radius - inner_radius)) + 1)
        radii = np.linspace(
            inner_radius,
            outer_radius,
            radial_samples,
            dtype=np.float32,
        )[:, None]
        angles = np.linspace(
            0.0,
            2.0 * np.pi,
            cls._ANGLE_BINS,
            endpoint=False,
            dtype=np.float32,
        )[None, :]
        map_x = center_x + radii * np.sin(angles)
        map_y = center_y - radii * np.cos(angles)
        return cv2.remap(
            image,
            map_x,
            map_y,
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )

    @staticmethod
    def _circular_edge_response(values, sample_width, axis=-1):
        after = np.zeros_like(values)
        before = np.zeros_like(values)
        for offset in range(sample_width):
            after += np.roll(values, -offset, axis=axis)
            before += np.roll(values, offset + 1, axis=axis)
        return (after - before) / sample_width

    @staticmethod
    def _circular_window_mean(values, window_size):
        extended = np.concatenate((values, values[:window_size - 1]))
        return np.convolve(
            extended,
            np.ones(window_size, dtype=np.float32) / window_size,
            mode="valid",
        )

    @staticmethod
    def _normalize_candidates(values, candidate_indices):
        normalized = np.zeros_like(values, dtype=np.float32)
        candidate_values = values[candidate_indices]
        minimum = float(np.min(candidate_values))
        value_range = float(np.max(candidate_values)) - minimum
        if value_range > 1e-6:
            normalized[candidate_indices] = (
                candidate_values - minimum
            ) / value_range
        return normalized

    @staticmethod
    def _circular_smooth(values, kernel_size):
        padding = kernel_size // 2
        extended = np.concatenate((values[-padding:], values, values[:padding]))
        kernel = np.ones(kernel_size, dtype=np.float32) / kernel_size
        return np.convolve(extended, kernel, mode="valid")
