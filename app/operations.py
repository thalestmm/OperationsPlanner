from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty

from kivymd.app import MDApp

# CAPITAL INPUT CLASS FOR THE ICAO CODES
from kivymd.uix.textfield import MDTextField

# DEPARTURE TIME SELECTION
from kivymd.uix.pickers import MDTimePicker

# PROJECT DROPDOWN MENU
from kivymd.uix.list import OneLineListItem
from kivymd.uix.menu import MDDropdownMenu
from kivy.uix.colorpicker import get_color_from_hex

from app.Tools import Tools

from datetime import datetime, time

import logging


# AUXILIARY CLASSES CREATION
class IconListItem(OneLineListItem):
    icon = StringProperty()


class MDTextField(MDTextField):

    def insert_text(self, substring, from_undo=False):
        s = substring.upper()

        return super().insert_text(s, from_undo=from_undo)


# APP CLASS
class OperationsApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.build_version = '0.2.0'

        self.takeoff_time = None

        self.theme_cls.theme_style = "Dark"

        self.screen = Builder.load_file(r'app/operations.kv')

        self.usage_tools = Tools()
        self.available_projects = self.usage_tools.projects_names

        dropdown_menu_items = [
            {
                "viewclass": "IconListItem",
                "icon": "airplane",
                "height": dp(56),
                "text": f"       {project}",
                "on_release": lambda x=f"{project}": self.set_project(x),
            } for project in self.available_projects]

        self.menu = MDDropdownMenu(
            caller=self.screen.ids.project_selection,
            items=dropdown_menu_items,
            position="bottom",
            width_mult=4,
        )

    def build(self):
        return self.screen

    def show_time_picker(self):

        previous_time = time(12,0,0)

        time_dialog = MDTimePicker(primary_color=get_color_from_hex("#ffc30b"),
                                    accent_color=get_color_from_hex("#f6f6f6"),
                                    text_button_color=get_color_from_hex("#000000"),
                                    text_toolbar_color=get_color_from_hex("#000000"),
                                    text_color=("#000000"))

        time_dialog.set_time(previous_time)
        time_dialog.bind(on_cancel=self.on_cancel, time=self.get_time)
        time_dialog.open()

    def get_time(self, instance, time):
        '''
        The method returns the set time.

        :type instance: <kivymd.uix.picker.MDTimePicker object>
        :type time: <class 'datetime.time'>
        '''
        self.screen.ids.takeoff_time.text = "DEP " + str(time)  + " Z"
        self.takeoff_time = time

        return time

    def on_cancel(self, instance, time):
        self.screen.ids.takeoff_time.text = "Selecione um horário"

    def set_project(self, text__item):
        self.screen.ids.project_selection.text = text__item
        self.menu.dismiss()

    def switch_themes(self):
        if self.theme_cls.theme_style == "Light":
            self.theme_cls.theme_style = "Dark"
        else:
            self.theme_cls.theme_style = "Light"

    def add_leg(self, i: int = 0, last_arr: str = 'SBCO'):
        leg_id = i + 1

        if i == 0:
            default_dep = ''
        else:
            default_dep = last_arr
            # self.store_leg_values(dep=self.screen.ids.flight_planner_layout.ids.leg.ids.dep.text,
            #                       arr=self.screen.ids.flight_planner_layout.ids.leg.ids.arr.text,
            #                       alt=self.screen.ids.flight_planner_layout.ids.leg.ids.alt.text)


        # if leg_id == 1:
        #     pass
        # else:
        #     self.last_arr = self.screen.ids[f'arr_{self.counter}'].text

        KV = f"""
MDGridLayout:
    id: leg
    cols: 4
    size_hint: (0.8,1)
    pos_hint: {{'center_x': 0.5}}
    adaptive_height: True
    adaptive_width: True
    size_hint_y: None
    height: self.minimum_height
    spacing: [30,0]
    
    MDLabel:
        text: '{leg_id}.'
        size: (20,20)
        size_hint_x: None
        width: 45
    CapitalStringICAO:
        id: dep
        hint_text: 'DEP'
        text: '{self.last_arr}'
        size_hint_x: None
        width: 100
        write_tab: False
        max_text_length: 4
        # on_validate: self.set_icao(self.text, 'dep_{leg_id}')
    CapitalStringICAO:
        id: arr
        hint_text: 'ARR'
        size_hint_x: None
        width: 100
        write_tab: False
        max_text_length: 4
    CapitalStringICAO:
        id: alt
        hint_text: 'ALT'
        size_hint_x: None
        width: 100
        write_tab: False
        max_text_length: 4
        """

        leg_kv = Builder.load_string(KV, rulesonly=False)
        print(Builder.rule)

        self.screen.ids.flight_planner_layout.add_widget(leg_kv)

        logging.info(f"leg {leg_id} added")

        self.counter += 1

        return leg_id + 1

    def clear_planner(self):
        for i in range(10):
            self.screen.ids[f'dep_{i + 1}'].text = ''
            self.screen.ids[f'arr_{i + 1}'].text = ''
            self.screen.ids[f'alt_{i + 1}'].text = ''

    def export_flight_plan(self):
        data_export = []

        for i in range(10):
            dep = self.root.ids[f'dep_{i + 1}'].text.upper()
            arr = self.root.ids[f'arr_{i + 1}'].text.upper()
            alt = self.root.ids[f'alt_{i + 1}'].text.upper()

            if dep != '' and arr != '':
                data_export.append((dep,arr,alt))

        trip_weight  = int(self.root.ids.trip_weight.text)
        project      = self.root.ids.project_selection.text
        takeoff_time = self.root.ids.takeoff_time.text.lstrip("DEP ").rstrip(" Z")

        self.usage_tools.full_planner_export(data_export=data_export, trip_weight=trip_weight, project=project,
                                             takeoff_time=takeoff_time)



if __name__ == "__main__":
    app = OperationsApp()
    app.run()
