"""Task page with an optional exclusive On-demand filter."""

from PySide6.QtWidgets import QCheckBox

from ok import Config, og
from ok.ui.qt.tasks import tasks_page


class GroupedTasksPage(tasks_page.TasksPage):
    def __init__(self, *args, **kwargs):
        self.group_filter_config = Config(
            "grouped_task_filter", {"show_grouped_in_onetime": False}
        )
        super().__init__(*args, **kwargs)

        self.show_grouped_checkbox = QCheckBox(
            og.app.tr("Show grouped tasks in On-demand"), self
        )
        self.show_grouped_checkbox.setChecked(self._show_grouped())
        self.show_grouped_checkbox.toggled.connect(self._set_show_grouped)
        self.layout().insertWidget(1, self.show_grouped_checkbox)
        self.filter_tabs.current_changed.connect(self._update_checkbox_visibility)
        self._update_checkbox_visibility()

    def _show_grouped(self):
        return self.group_filter_config["show_grouped_in_onetime"]

    def _set_show_grouped(self, show):
        self.group_filter_config["show_grouped_in_onetime"] = show
        self._build_filters()
        self._apply_filter()

    def _update_checkbox_visibility(self, _key=None):
        self.show_grouped_checkbox.setVisible(
            self.current_filter() == tasks_page.KIND_ONETIME
        )

    def _build_filters(self):
        super()._build_filters()
        if not self._show_grouped() and tasks_page.KIND_ONETIME in self.filter_tabs.keys():
            count = sum(not getattr(task, "group_name", None) for task in self.onetime_tasks)
            self.filter_tabs.set_count(tasks_page.KIND_ONETIME, count)

    def _apply_filter(self):
        key = self.current_filter()
        for section in (self.onetime_section, self.trigger_section):
            shown = 0
            for row in section.rows:
                visible = tasks_page.matches_filter(row.task, key, row.is_trigger)
                if (key == tasks_page.KIND_ONETIME and not self._show_grouped()
                        and getattr(row.task, "group_name", None)):
                    visible = False
                row.setVisible(visible)
                shown += visible
            section.setVisible(shown > 0)
            section.set_count_text(str(shown))
            section.set_collapsible(key == tasks_page.KIND_ALL)
        self._title_sections(key)
        if self.selected_task in self.rows and self.rows[self.selected_task].isHidden():
            first = next(
                (row.task for section in (self.onetime_section, self.trigger_section)
                 for row in section.rows if not row.isHidden()),
                None,
            )
            self.select_task(first)
        self._layout_sections()


def install_grouped_task_filter():
    tasks_page.TasksPage = GroupedTasksPage
