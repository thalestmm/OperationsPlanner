import pandas as pd
from haversine import haversine, Unit
from math import ceil
import logging
from fpdf import FPDF
from datetime import time, date


class Tools:
    def __init__(self, path_adjustment: str = ""):
        # ADD THE CURRENT PATH FOR TESTING PURPOSES
        self.testing_path = path_adjustment

        # ICAO CSV FILEPATH
        self.icao_filepath = self.testing_path + r'app/Dependencies/icao_exports.csv'

        # INITIALIZE DATAFRAME FOR COORDINATES REQUEST
        self.icao_df = pd.read_csv(self.icao_filepath, index_col="index").drop(columns="coordinates")

        # MEMORY MANAGEMENT
        self.icao_df.longitude = self.icao_df.longitude.astype("float16")
        self.icao_df.latitude = self.icao_df.latitude.astype("float16")

        # PROJECTS CSV FILEPATH
        self.projects_filepath = self.testing_path + r"app/Dependencies/projects.csv"

        # INITIALIZE DATAFRAME FOR PROJECTS REQUESTS
        self.projects_df = pd.read_csv(self.projects_filepath)
        self.projects_df["available"] = self.projects_df.max_to_weight - self.projects_df.weight

        # PROJECT NAMES FOR VERIFICATION
        self.projects_names = ["C-95 2330", "C-95 2339", "C-95 2341", "C-97 2008", "C-98 2743"]

        logging.info("Tools Class instantiated")

    def get_coordinates(self, ICAO_id: str, DataFrame=None):
        # USE THE ICAO DATAFRAME AS DEFAULT
        DataFrame = self.icao_df

        # STANDARDIZE ALL INPUTS
        ICAO_id = ICAO_id.lstrip(" ")
        ICAO_id = ICAO_id.rstrip(" ")
        ICAO_id = ICAO_id.upper()

        # SEARCH DATAFRAME FOR THE DESIRED ICAO ID
        localizer = DataFrame.loc[DataFrame.gps_code == ICAO_id]

        # HANDLE MISSING ICAO CODES OR TYPOS
        if localizer.empty:
            logging.error("Indicativo não encontrado no banco de dados")
            raise KeyError("Aeródromo não encontrado no banco de dados, verifique a grafia")

        # RETURN THE LATITUDE AND LONGITUDE OF THE DESIRED ICAO ID
        logging.info(f"Coordinates for {ICAO_id} generated")
        return float(localizer.latitude), float(localizer.longitude)

    def get_distance(self, ICAO_1: str, ICAO_2: str) -> float:
        coords_1 = self.get_coordinates(ICAO_1)
        coords_2 = self.get_coordinates(ICAO_2)

        return float(haversine(coords_1, coords_2, unit=Unit.NAUTICAL_MILES))

    def get_project_params(self, project: str, DataFrame=None):
        # VALIDATE THE PROJECT NAME
        if project not in self.projects_names:
            raise KeyError

        # USE THE PROJECTS DATAFRAME AS DEFAULT
        DataFrame = self.projects_df

        # SEARCH THE DATAFRAME FOR THE PROJECT
        localizer = DataFrame.loc[DataFrame.project == project]

        # ALL PARAMETERS TO BE RETURNED
        spd_low = int(localizer.spd_low)
        spd_high = int(localizer.spd_high)
        weight = int(localizer.weight)
        max_fuel = int(localizer.max_fuel)
        burn = int(localizer.burn)
        max_to_weight = int(localizer.max_to_weight)
        fuel_unit = int(localizer.fuel_unit)
        available = float(localizer.available)

        return spd_low, spd_high, weight, max_fuel, burn, max_to_weight, fuel_unit, available

    @staticmethod
    def get_time_from_distance_minutes(distance: float, spd_low: int, spd_high: int = None) -> int:
        # LONG RANGE FLIGHTS WILL TAKE THE HIGH SPEED
        if distance > 740:
            time = ceil((distance / spd_high) * 60)

        # REGULAR RANGE FLIGHTS USE THE LOW SPEED
        else:
            time = ceil((distance / spd_low) * 60)

        if time % 10 == 0:
            rounded_time_in_minutes = time
        else:
            time = time // 5
            rounded_time_in_minutes = (time * 5) + 5

        return rounded_time_in_minutes

    @staticmethod
    def prettify_time(time_in_minutes: int) -> str:
        return "{:02d}:{:02d}".format(*divmod(time_in_minutes, 60))

    @staticmethod
    def minimum_fuel_per_leg(main_time: int, altn_time: int, burn: int) -> int:
        burn_per_minute = burn / 60

        main_burn = main_time * burn_per_minute
        altn_burn = altn_time * burn_per_minute

        total_burn = main_burn + altn_burn + (45 * burn_per_minute)

        return ceil(total_burn)

    @staticmethod
    def get_available_cargo_weight_per_leg(minimum_fuel: int, available: float, fuel_unit: int, trip_weight: int):
        if fuel_unit == 0:
            fuel = minimum_fuel * 0.45
        else:
            fuel = minimum_fuel

        return available - fuel - trip_weight

    def check_icao_on_dataset(self, leg_icao_list: list) -> list:
        unknown_icao = []
        for icao in leg_icao_list:
            try:
                self.get_coordinates(icao)
            except KeyError:
                unknown_icao.append(icao)

        return unknown_icao

    def full_planner_export(self, data_export: list, trip_weight: int, project: str, takeoff_time: str):  # NOT DONE
        # HANDLE MISSING ARGUMENTS FOR PROJECT
        if project not in self.projects_names:
            # SET C-95 2330 AS DEFAULT
            project = self.projects_names[0]

        # GET PROJECT PARAMETERS
        spd_low, spd_high, weight, max_fuel, burn, max_to_weight, fuel_unit, available = self.get_project_params(
            project)

        # HANDLE MISSING TAKEOFF TIME
        if takeoff_time == "Selecione um horário":
            takeoff_time = "09:00:00"

        hours = int(takeoff_time.split(':')[0])
        minutes = int(takeoff_time.split(':')[1])

        takeoff_time = time(hours, minutes, 0)

        leg_n = 0

        project_model = project.split(" ")[0]
        self.create_pdf_doc(project_model)

        total_flight_hours = 0

        for leg in data_export:
            unknown_icao = self.check_icao_on_dataset(leg)

            if len(unknown_icao) > 0:
                self.add_error_message_inline(unknown_icao, leg_n)

                leg_n += 1
                continue

            icao_1    = leg[0]
            icao_2    = leg[1]
            icao_altn = leg[2]

            # DISTANCE BETWEEN DEPARTURE AND ARRIVAL
            main_distance = self.get_distance(icao_1, icao_2)
            main_time     = self.get_time_from_distance_minutes(main_distance, spd_low, spd_high)

            # DISTANCE BETWEEN ARRIVAL AND ALTERNATIVE
            altn_distance = self.get_distance(icao_2, icao_altn)
            altn_time     = self.get_time_from_distance_minutes(altn_distance, spd_low, spd_high)

            # GET FUEL PARAMETERS
            required_fuel = self.minimum_fuel_per_leg(main_time, altn_time, burn)

            # GET AVAILABLE WEIGHT
            available_weight = self.get_available_cargo_weight_per_leg(required_fuel, available, fuel_unit, trip_weight)

            # MANAGE LIMIT EXTRAPOLATIONS
            if required_fuel > max_fuel or available_weight < 0:
                self.pdf.set_text_color(255, 0, 0)

            # ADAPT VALUES FOR PDF PRINTING
            leg_counter      = f'{leg_n + 1}.'
            update_y_pos     = 20 + (leg_n * 13)
            flight_time      = self.prettify_time(main_time)
            to_altn_time     = self.prettify_time(altn_time)
            required_fuel    = str(required_fuel)
            available_weight = str(int(available_weight))

            flight_hours, flight_minutes = divmod(main_time + takeoff_time.minute, 60)

            if takeoff_time.hour + flight_hours >= 24:
                estimate_arrival = time(takeoff_time.hour + flight_hours - 24, flight_minutes, 0)
            else:
                estimate_arrival = time(takeoff_time.hour + flight_hours, flight_minutes, 0)

            self.add_planner_row(update_y_pos, leg_counter, str(takeoff_time), icao_1, str(estimate_arrival),
                                 icao_2, flight_time, icao_altn, to_altn_time, required_fuel, available_weight)

            if takeoff_time.hour + flight_hours + 1 >= 24:
                takeoff_time = time(takeoff_time.hour + flight_hours + 1 - 24, flight_minutes, 0)
            else:
                takeoff_time = time(takeoff_time.hour + flight_hours + 1, flight_minutes, 0)

            total_flight_hours += main_time

            leg_n += 1

        total_working_hours = total_flight_hours + 60 * (leg_n)
        total_working_hours = self.prettify_time(total_working_hours)

        self.add_total_working_hours(total_working_hours)

        total_flight_hours  = self.prettify_time(total_flight_hours)

        self.add_total_flight_hours(total_flight_hours)

        # EXPORT PDF FILE
        self.pdf.output(f'Planejamento {project_model} - {date.today()}.pdf')

        return None

    def add_error_message_inline(self, unknown_icao: list, leg_n: int):
        print("Working")
        base_x_pos = 25
        new_y_pos = 55 + (leg_n * 13)
        plural = 'ENCONTRADOS' if len(unknown_icao) > 1 else 'ENCONTRADO'
        airports = f'{unknown_icao[0]}'
        for icao in unknown_icao[1:]:
            airports += f', {icao}'

        self.pdf.set_text_color(255, 0, 0)
        self.pdf.text(base_x_pos + 0, new_y_pos, f'{leg_n + 1}.')
        self.pdf.text(base_x_pos + 10, new_y_pos, f'{airports} NÃO {plural}')

        self.pdf.set_text_color(0, 0, 0)
        self.pdf.line(base_x_pos - 2, new_y_pos + 4, 182, new_y_pos + 4)

    def create_pdf_doc(self, project_model):
        self.page_width = 210
        self.page_height = 297
        self.pdf = FPDF()
        self.pdf.set_creator("Ten Av Thales")
        self.pdf.set_author("Ten Av Thales")
        self.pdf.add_page()
        self.pdf.set_font("Arial", "B", 22)

        self.pdf.cell(195, 40, txt=project_model, align="C")
        self.add_planner_header()

    def add_planner_header(self):
        base_x_pos = 25

        new_y_pos = 45

        self.pdf.set_font("Arial", "B", 12)

        self.pdf.text(base_x_pos + 0, new_y_pos, 'nº')
        self.pdf.text(base_x_pos + 10, new_y_pos, 'HORA Z')

        self.pdf.text(base_x_pos + 48, new_y_pos, 'ETA')

        self.pdf.text(base_x_pos + 85, new_y_pos, 'TEV')

        self.pdf.text(base_x_pos + 116, new_y_pos, 'TALT')

        self.pdf.text(base_x_pos + 131, new_y_pos, 'CMB')

        self.pdf.text(base_x_pos + 145, new_y_pos, 'DISP')

        self.pdf.text(base_x_pos + 32, new_y_pos, 'DEP')
        self.pdf.text(base_x_pos + 70, new_y_pos, 'ARR')
        self.pdf.text(base_x_pos + 100, new_y_pos, 'ALTN')

    def add_planner_row(self, update_y_pos, leg_counter, takeoff_time, departure, estimate_arrival,
                        arrival, flight_time, alternative, time_to_altn, minimum_fuel, available_weight):
        base_y_pos = 35
        base_x_pos = 25

        new_y_pos = base_y_pos + update_y_pos

        self.pdf.set_font("Arial", size=13)

        self.pdf.text(base_x_pos + 0, new_y_pos, leg_counter)
        self.pdf.text(base_x_pos + 10, new_y_pos, takeoff_time)

        self.pdf.text(base_x_pos + 48, new_y_pos, estimate_arrival)

        self.pdf.text(base_x_pos + 85, new_y_pos, flight_time)

        self.pdf.text(base_x_pos + 116, new_y_pos, time_to_altn)

        self.pdf.text(base_x_pos + 131, new_y_pos, minimum_fuel)

        self.pdf.text(base_x_pos + 145, new_y_pos, available_weight)

        self.pdf.set_font("Arial", "B", 13)

        self.pdf.text(base_x_pos + 32, new_y_pos, departure)
        self.pdf.text(base_x_pos + 70, new_y_pos, arrival)
        self.pdf.text(base_x_pos + 100, new_y_pos, alternative)

        self.pdf.line(base_x_pos - 2, new_y_pos + 4, 182, new_y_pos + 4)

        self.pdf.set_text_color(0, 0, 0)

    def add_total_flight_hours(self, total_flight_hours: str):
        self.pdf.set_font("Arial", "", 12)
        self.pdf.text(25, 35, f'ESFORÇO AÉREO: {total_flight_hours}')

    def add_total_working_hours(self, total_working_hours: str):
        self.pdf.set_font("Arial", '', 12)
        self.pdf.text(140, 35, f'ETAPA TOTAL: {total_working_hours}')

    def get_all_available_altn(self):
        pass

    def find_nearest_altn(self, icao_arr: str):
        pass

    def get_total_time_spent(self):
        pass


if __name__ == "__main__":
    pass