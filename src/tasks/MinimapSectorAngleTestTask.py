import time

import cv2
import numpy as np

from src.tasks.SRTask import SRTask


class SectorNotDetectedError(RuntimeError):
    """当前帧没有找到满足硬性边界条件的扇形。"""

    pass


class MinimapSectorAngleTestTask(SRTask):
    """识别小地图中半透明白色扇形的中心朝向。

    角度约定：画面正上方为 0°，顺时针方向递增。算法先将圆形区域
    展开成“半径 × 角度”的极坐标采样矩阵，再寻找相隔固定扇形宽度
    的“暗到亮”和“亮到暗”边界，最后用遮罩的两项白度特征排序。
    """

    # 小地图截图区域，格式为 (左, 上, 右, 下)，使用相对于游戏画面的
    # 0～1 比例坐标，因此能随目标窗口分辨率等比例缩放。
    MINIMAP_REGION = (71/2560,47/1440, 295/2560, 271/1440)

    # 将完整圆周离散成 360 份，即每个角度索引约等于 1°。
    _ANGLE_BINS = 360
    # 检测圆半径占截图区域半径的比例。0.5 表示检测圆的直径为截图区域
    # 宽度/高度的一半，圆外的四角和外围地图内容不会参与计算。
    _DETECTION_RADIUS_RATIO = 0.50
    # 排除小地图正中心的角色图标区域：1440p 下半径为 15 像素，运行时
    # 按实际游戏画面高度等比例缩放（1080p 为 11.25 像素）。
    _CENTER_EXCLUSION_RADIUS = 15.0 / 1440
    # 探针终点相对于检测圆半径的比例；1 表示延伸到检测圆边缘。
    _OUTER_RADIUS_RATIO = 1
    # 单条径向探针与顺时针方向的下一条探针之间的角度步长。当前为 1°，
    # 不会对多条相邻探针求平均，因此探针本身没有额外角宽。
    _EDGE_SAMPLE_WIDTH_DEGREES = 1
    # 一条边界至少要让 75% 的径向采样点同向变白/变暗，才认为整条线
    # 发生了遮罩边界变化，而不是局部道路、图标或地图纹理。
    _MIN_EDGE_POINT_CONSISTENCY = 0.75
    # 亮边与暗边强度的几何平均下限，用于过滤数值抖动和极弱伪边界。
    _MIN_PAIRED_EDGE_SCORE = 2e-4
    # 通过硬性边界筛选后，最终候选排序的两项权重。
    _CENTER_WHITENESS_WEIGHT = 0.35
    _INSIDE_OUTSIDE_WHITENESS_WEIGHT = 0.65
    _SECTOR_WIDTH_DEGRESS = 92

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Minimap Sector Angle Test"
        self.description = "Continuously estimates the translucent sector angle on the minimap."

    def run(self):

        # 裁剪小地图的区域
        region = self.box_of_screen(*self.MINIMAP_REGION)
        while True:
            # 每轮主动刷新游戏画面，再从同一比例区域裁出小地图。
            self.next_frame()
            minimap = region.crop_frame(self.frame)
            # 中心排除半径。
            center_exclusion_radius = (self._CENTER_EXCLUSION_RADIUS * self.frame.shape[0])
            # perf_counter 适合测量短时间间隔，不受系统时间校准影响。
            detection_started_at = time.perf_counter()
            try:
                angle, confidence, metrics = self._estimate_sector_angle(
                    minimap,
                    self._SECTOR_WIDTH_DEGRESS,
                    center_exclusion_radius,
                )
            except SectorNotDetectedError as error:
                # 未检测到属于正常帧状态：清空上一次成功结果的详细指标，
                # 不抛出异常，下一帧继续尝试。
                self.info["Sector Angle"] = "Not detected"
                self.info["Confidence"] = "0.00"
                self.info["Detection Status"] = str(error)
                for key in self._metric_info_keys():
                    self.info[key] = "-"
            else:
                # 所有指标均对应最终胜出的同一组亮边/暗边候选。
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
            # 使用框架的可中断 sleep，使任务被禁用时能够及时退出。
            self.sleep(0.05)

    @staticmethod
    def _metric_info_keys():
        """返回识别失败时需要清空的详细指标名称。"""

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
        """计算单帧中的扇形角度、置信度和调试指标。

        ``sector_width_degrees`` 是亮边到暗边的顺时针角距离；当前任务
        传入 92°。找不到完整边界组合时抛出专用异常，由 ``run`` 转换为
        info 中的“Not detected”，而输入区域非法仍作为真实配置错误处理。
        """

        if image is None or image.size == 0:
            raise ValueError("Minimap region is empty.")

        # 无论截图是否完全为正方形，都以短边确定圆半径，从而保证计算
        # 区域始终是圆形，不会读到矩形四角。
        height, width = image.shape[:2]
        center_x = (width - 1) / 2.0
        center_y = (height - 1) / 2.0
        region_radius = min(width, height) / 2.0
        detection_radius = region_radius * cls._DETECTION_RADIUS_RATIO

        # 归一化到 0～1。白色遮罩会同时抬高 B/G/R，取三个通道的最小值
        # 作为“白度”可压制高饱和的蓝色、紫色任务图标。
        normalized_color = image.astype(np.float32) / 255.0
        whiteness = np.min(normalized_color, axis=2)

        # 探针是一条从 inner_radius 到 outer_radius 的径向线；中心圆和
        # 检测圆之外的像素完全不参与计算。
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
        # polar_whiteness 的行表示不同半径、列表示不同角度。沿半径取
        # 中位数，可避免少数半径上的亮图标支配整条角度探针。
        angle_score = np.median(polar_whiteness, axis=0)
        # 圆周信号首尾相接，必须用环形平滑避免 359°/0° 处断裂。
        angle_score = cls._circular_smooth(angle_score, 7)

        # 把扇形角宽换算成角度采样格数量。window_score 表示从每个角度
        # 开始、顺时针覆盖完整扇形宽度后的平均白度。
        window_size = max(
            1,
            round(cls._ANGLE_BINS * sector_width_degrees / 360.0),
        )
        window_score = cls._circular_window_mean(angle_score, window_size)

        # 半透明白色扇形的起点是“暗→亮”，终点是“亮→暗”。edge_width
        # 控制比较当前探针与前方多少度的探针，当前配置等价于相邻两线。
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
        # 对每个半径分别计算角向白度差，得到形状为“半径 × 角度”的
        # 边缘响应；正数表示顺时针跨过该位置后变白，负数表示变暗。
        radial_whiteness_edge = cls._circular_edge_response(
            polar_whiteness,
            edge_width,
            axis=1,
        )
        # 覆盖率统计整条径向探针上同向变化的点数比例。亮边看正数，暗边
        # 看负数；这是候选必须满足的硬条件，不参与后续加权补偿。
        enter_consistency = np.mean(radial_whiteness_edge > 0.0, axis=0)
        leave_consistency = np.mean(radial_whiteness_edge < 0.0, axis=0)
        # 使用中位数表示整条线的边缘强度，局部异常点不会显著影响结果。
        enter_edge_score = np.median(radial_whiteness_edge, axis=0)
        leave_edge_score = np.median(-radial_whiteness_edge, axis=0)
        # 亮暗边强度取几何平均：任意一边为零，整组配对分数即为零，避免
        # 一条很强的道路边缘补偿另一条不存在的边界。
        paired_edge_score = np.sqrt(
            np.maximum(enter_edge_score, 0.0)
            * np.maximum(leave_edge_score[sector_end_indices], 0.0)
        )

        # 从 0° 开始顺时针逐度旋转探针。发现合格亮边后，只检查顺时针
        # 相隔一个扇形宽度的位置是否为合格暗边，并保存完整组合。
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
        # 没有候选是正常识别失败，不应终止持续运行的测试任务。
        if not edge_pairs:
            raise SectorNotDetectedError(
                "No complete bright/dark sector edge pair was found."
            )
        candidate_indices = np.array(
            [start_index for start_index, _ in edge_pairs],
            dtype=np.int32,
        )

        # 特征一：遮罩越靠近中心越白。把径向采样分成三段，仅比较最内
        # 1/3 和最外 1/3，减少中段图标对渐变趋势的影响。
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
        # 特征二：扇形内部应比扇形外部更白。outside_score 从整个圆周
        # 总白度中扣除当前扇形窗口，再除以剩余角度数。
        if window_size < cls._ANGLE_BINS:
            outside_score = (
                np.sum(angle_score) - window_score * window_size
            ) / (cls._ANGLE_BINS - window_size)
            inside_outside_score = window_score - outside_score
        else:
            inside_outside_score = window_score

        # 两项原始分数的量纲/范围不同，先只在已通过边缘硬条件的候选中
        # 分别归一化到 0～1，再按配置权重组合。非候选保持为负无穷。
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

        # 扇形朝向定义为亮边起点与暗边终点之间的中心角，并使用取模处理
        # 跨越 359°→0° 的扇形。
        sector_start = int(np.argmax(final_score))
        sector_center = (sector_start + window_size / 2.0) % cls._ANGLE_BINS
        angle = sector_center * 360.0 / cls._ANGLE_BINS
        # 置信度表示最终候选的配对边缘强度相对于本帧最强配对边缘的比例。
        # 它不是概率，仅用于观察当前结果的相对边缘质量。
        confidence = (
            float(paired_edge_score[sector_start])
            / (float(np.max(paired_edge_score)) + 1e-6)
        )
        sector_end = int(sector_end_indices[sector_start])
        # 返回原始指标而非只返回归一化值，便于在 self.info 中调试阈值。
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
        """把圆形采样环展开为“半径 × 顺时针角度”的矩阵。

        第 0 列指向画面正上方，列索引递增时探针顺时针旋转。使用
        ``cv2.remap`` 双线性插值读取非整数坐标，因此不同分辨率下仍能
        获得连续且固定数量的角度样本。
        """

        # 径向样本间隔约为 1 像素，并确保极窄区域仍至少有两个点。
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
        # 0° 朝上、顺时针为正时：x 使用 sin，y 使用负 cos。
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
        """计算环形序列当前位置前后两侧的均值差。

        返回正值表示沿指定轴跨过当前位置后变亮，负值表示变暗；roll
        天然处理圆周首尾连接，不会在 0° 产生特殊分支。
        """

        after = np.zeros_like(values)
        before = np.zeros_like(values)
        for offset in range(sample_width):
            after += np.roll(values, -offset, axis=axis)
            before += np.roll(values, offset + 1, axis=axis)
        return (after - before) / sample_width

    @staticmethod
    def _circular_window_mean(values, window_size):
        """计算每个起始角对应的顺时针环形窗口平均值。"""

        # 把序列开头复制到末尾，使跨越 360° 的窗口仍可直接卷积。
        extended = np.concatenate((values, values[:window_size - 1]))
        return np.convolve(
            extended,
            np.ones(window_size, dtype=np.float32) / window_size,
            mode="valid",
        )

    @staticmethod
    def _normalize_candidates(values, candidate_indices):
        """仅对合格候选做 0～1 最小-最大归一化。

        所有候选分数完全相同时保持为 0，避免除零；非候选始终为 0，
        调用方会使用 candidate_indices 将它们排除在最终评分之外。
        """

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
        """使用移动平均平滑一维圆周信号，同时保持输出长度不变。"""

        padding = kernel_size // 2
        extended = np.concatenate((values[-padding:], values, values[:padding]))
        kernel = np.ones(kernel_size, dtype=np.float32) / kernel_size
        return np.convolve(extended, kernel, mode="valid")
