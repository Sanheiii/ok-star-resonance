from src.tasks.DungeonTasks.DungeonTaskBase import DungeonTaskBase, Difficulty


class Dungeon1343Task(DungeonTaskBase):

    INSTRUMENT_POSITION = (422.870, -6.900)

    def __init__(self, *args, **kwargs):
        self.task_name = 'Delusion - Shadow Fortress - Hard'
        self.task_name_zh = '弥妄·黯影堡垒 - 困难'
        self.task_desc = 'Tank classes are not supported.'
        self.task_desc_zh = '不支持守护职业。'
        self.difficulty = Difficulty.HARD
        self.has_normal_difficulty = False
        super().__init__(*args, **kwargs)

    def run(self):
        super().run()
        while True:
            if not self.exec():
                self.return_to_initial_state()

    def exec(self):
        if not self.begin():
            return False
        self.investigate(self.INSTRUMENT_POSITION)

        if not self._follow_route((
                (422.472, -1.512),
                (420.635, 2.635),
                (414.624, 3.651),
                (402.965, -7.175),
                (418.629, -27.210),
                (420.580, -60.080),
                (431.590, -52.940)
        ), '前往第一处战斗'):
            return False
        if not self._wait_for_combat_end('第一处战斗'):
            return False

        self.send_key(self.get_custom_key('Auto Battle'))

        if not self._clear_corruption(
                ((431.590, -52.940),), '第一次清除侵蚀'):
            return False

        if not self._follow_route((
                (418.216, -61.360),
                (427.234, -83.393),
        ), '前往第一处门槛'):
            return False
        if not self._jump_over_threshold():
            return False

        if not self._follow_route((
                (431.375, -92.830),
                (441.263, -87.945),
                (436.530, -89.730),
        ), '前往第一处低重力装置'):
            return False
        self.send_key('w', down_time=0.2, after_sleep=1)
        self.info['State'] = '借助低重力装置前往楼上'
        self.send_key('space', after_sleep=2)
        self.send_key('space', after_sleep=2)
        self.send_key('w', down_time=2, after_sleep=1)

        if not self._follow_route((
                (419.585, -89.677),
        ), '前往第二处战斗'):
            return False
        if not self._wait_for_combat_end('第二处战斗'):
            return False

        if not self._clear_corruption((
                (419.585, -89.677),
                (402.926, -98.493),
                (397.057, -114.074),
        ), '第二次清除侵蚀'):
            return False

        if not self._follow_route(
                ((395.480, -131.100),), '前往第二处低重力装置'):
            return False
        self.send_key('w', down_time=0.2, after_sleep=1)
        if not self._wait_until_below_height(245):
            return False

        if not self._follow_route((
                (389.717, -150.857),
                (402.900, -169.730),
                (413.112, -183.464),
        ), '前往第三处战斗'):
            return False
        if not self._wait_for_combat_end('第三处战斗'):
            return False

        if not self._clear_corruption(
                ((402.900, -169.730),), '第三次清除侵蚀'):
            return False
        if not self._jump_floating_platform():
            return False

        self.move_to_position(self.position, (437.503, -152.330), 1,1)
        self.send_key(self.get_custom_key('Toggle Walk/Run'), after_sleep=0.5)
        if not self._follow_route((
                (429.543, -138.043),
        ), '跳楼并前往第四处战斗', enable_sprint = False):
            return False
        self.send_key(self.get_custom_key('Toggle Walk/Run'), after_sleep=0.5)

        if not self._follow_route((
                (437.742, -156.903),
                (456.451, -173.201),
        ), '前往第四处战斗'):
            return False
        if not self._wait_for_combat_end('第四处战斗'):
            return False

        if not self._follow_route((
                (459.943, -174.894),
                (481.500, -148.294),
                (488.071, -147.281),
                (488.569, -126.963),
        ), '前往Boss房'):
            return False
        if not self._jump_from_building():
            return False
        self.sleep(2)
        if not self._jump_to_boss_platform():
            return False

        self.info['State'] = '跳过Boss出场动画'
        for _ in range(3):
            self.send_key('esc', after_sleep=2)
            self.next_frame()
            if self.find_one('dungeon_scene_icon'):
                break

        self.sleep(1)

        self.send_key(self.get_custom_key('Phantom Dash'), after_sleep=1)
        self.click(0.5, 0.5, after_sleep=0.5)
        self.send_key(self.get_custom_key('Auto Battle'))

        if not self.wait_in_combat():
            self.log_error('Boss没有进入战斗')
            return False

        self.info['State'] = 'Boss战斗中'

        self.sleep(35)
        self.move_to_position(self.position, (565.530, -135.679))

        if not self._wait_for_combat_end('Boss战', time_out=420):
            return False

        self.info['State'] = '跳过Boss结算动画'
        for _ in range(3):
            self.send_key('esc', after_sleep=2)
            self.next_frame()
            if self.find_one('dungeon_scene_icon'):
                break

        return self.handle_end()

    def _follow_route(self, route, state, enable_sprint = True):
        self.info['State'] = state
        remaining = self.move_to_positions(
            route,
            node_tolerance=1,
            line_tolerance=1,
            max_path_deviation=8,
            enable_sprint=enable_sprint,
        )
        if remaining is not None:
            self.log_error(f'{state}移动失败，剩余路径: {remaining}')
            return False
        return True

    def _wait_for_combat_end(self, state, time_out=180):
        self.info['State'] = f'等待进入{state}'
        if not self.wait_in_combat():
            self.log_error(f'{state}没有进入战斗')
            return False
        self.info['State'] = f'{state}中'
        if not self.wait_out_of_combat(time_out=time_out):
            self.log_error(f'{state}超时')
            return False
        return True

    def _clear_corruption(self, route, state):
        if not self._follow_route(route, f'前往{state}'):
            return False
        self.info['State'] = state
        self.sleep(0.5)
        self.send_key('f', after_sleep=1)
        return True

    def _jump_over_threshold(self):
        self.info['State'] = '跳过第一处门槛'
        self.look_at(155)
        try:
            self.send_key_down('w', after_sleep=1)
            self.send_key('space', after_sleep=1)
        finally:
            self.send_key_up('w')
        return True

    def _wait_until_below_height(self, height):
        self.info['State'] = f'等待下落至Y坐标低于{height}'

        def is_below_height():
            position = self.position
            return position is not None and len(position) >= 3 and position[1] < height

        if self.wait_until(is_below_height, time_out=30):
            return True
        self.log_error(f'等待下落至Y坐标低于{height}超时')
        return False

    def _jump_floating_platform(self):
        self.info['State'] = '跳道中浮空平台'
        self.send_key('space', after_sleep=0.2)
        self.send_key('space', after_sleep=2)

        # 跳楼重置位置
        self.move_to_position(self.position, (409.220, -174.755), line_tolerance=1, target_tolerance=1)
        self.look_at(52)
        self.sleep(1)
        self.send_key('w', 2, after_sleep=2)
        self.rotate_camera(7.6)

        self.info['State'] = '跳过浮空平台'
        try:
            self.send_key_down('w', after_sleep=0.5)
            self.send_key('space', down_time=0.17, after_sleep=0.28)
            self.send_key('space', down_time=0.16, after_sleep=1.34)
            self.send_key('space', down_time=0.16, after_sleep=0.26)
            self.send_key('space', down_time=0.17, after_sleep=1.90)
            self.send_key('space', down_time=0.14, after_sleep=0.31)
            self.send_key('space', down_time=0.18, after_sleep=0.87)
        finally:
            self.send_key_up('w', after_sleep=1)
        return True

    def _jump_from_building(self):
        start_position = (479.790, -119.706)
        if not self._follow_route((start_position,), '前往第二处跳楼点'):
            return False
        self.info['State'] = '跳下第二处高台'
        self._look_at_twice(315)

        self.send_key_down('w', after_sleep=0.5) # key down 'w'
        self.send_key('space', down_time=0.21, after_sleep=1.26) # press key 'space'
        self.send_key_up('w', after_sleep=0.11) # key up 'w'
        self.send_key('s', down_time=0.33, after_sleep=0.21) # press key 's'
        self.send_key('w', down_time=1.77) # press key 'w'

        self.send_key(self.get_custom_key('Float'))
        self.sleep(1)
        self.click(0.5, 0.5)
        glide_key = 's' if self.get_custom_key('Invert Gliding Controls') else 'w'
        self.send_key(glide_key, down_time=3)

        if not self._wait_until_below_height(35):
            return False

        return True

    def _jump_to_boss_platform(self):
        self.info['State'] = '跳平台前往Boss房'

        # 跳楼重置位置
        self.move_to_position(self.position, (480.286, -114.664))
        self.look_at(97)
        self.send_key('w', 2, after_sleep=2)

        # 无移动速度加成
        self.send_key_down('w', after_sleep=0.16) # key down 'w'
        self.send_key_down('shift', after_sleep=0.43) # key down 'shift'
        self.send_key_down('space', after_sleep=0.19) # key down 'space'
        self.send_key_up('shift') # key up 'shift'
        self.send_key_up('space', after_sleep=0.57) # key up 'space'
        self.send_key_down('a', after_sleep=0.25) # key down 'a'
        self.send_key('space', down_time=0.18, after_sleep=0.37) # press key 'space'
        self.send_key_up('a', after_sleep=0.42) # key up 'a'
        self.send_key('space', down_time=0.18, after_sleep=0.12) # press key 'space'
        self.send_key('space', down_time=0.15, after_sleep=0.76) # press key 'space'
        self.send_key_down('d', after_sleep=0.10) # key down 'd'
        self.send_key('space', down_time=0.34, after_sleep=0.21) # press key 'space'
        self.send_key_up('d', after_sleep=0.84) # key up 'd'
        self.send_key('space', down_time=0.17, after_sleep=0.15) # press key 'space'
        self.send_key('space', down_time=0.15, after_sleep=0.69) # press key 'space'
        self.send_key_down('a') # key down 'a'
        self.send_key_up('w', after_sleep=0.87) # key up 'w'
        self.send_key_down('w') # key down 'w'
        self.send_key_down('space') # key down 'space'
        self.send_key_up('a', after_sleep=0.20) # key up 'a'
        self.send_key_up('space', after_sleep=0.15) # key up 'space'
        self.send_key('space', down_time=0.19, after_sleep=1.24) # press key 'space'
        self.send_key_up('w', after_sleep=1) # key up 'w'

        # self.send_key_down('w', after_sleep=0.18) # key down 'w'
        # self.send_key_down('shift', after_sleep=0.38) # key down 'shift'
        # self.send_key('space', down_time=0.26, after_sleep=0.13) # press key 'space'
        # self.send_key_up('shift', after_sleep=0.77) # key up 'shift'
        # self.send_key('space', down_time=0.21, after_sleep=0.33) # press key 'space'
        # self.send_key('space', down_time=0.19, after_sleep=0.27) # press key 'space'
        # self.send_key(self.get_custom_key('Float'), after_sleep=1.86)
        # self.send_key('space', down_time=0.22, after_sleep=0.27) # press key 'space'
        # self.send_key_down('space', after_sleep=0.16) # key down 'space'
        # self.send_key_down('a') # key down 'a'
        # self.send_key_up('space', after_sleep=0.82) # key up 'space'
        # self.send_key('space', down_time=0.22, after_sleep=0.14) # press key 'space'
        # self.send_key_up('a') # key up 'a'
        # self.send_key('space', down_time=0.14, after_sleep=1.00) # press key 'space'
        # self.send_key_up('w', after_sleep=2.19) # key up 'w'

        return True

    def _look_at_twice(self, direction):
        self.look_at(direction)
        self.sleep(1)
        self.look_at(direction)
