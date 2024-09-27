import pandas as pd
import datetime as dt
import numpy as np
import dateutil.parser as parser
from .genericCode import GenericCode
from itertools import product


class simulator():
    # VARIABLES GLOBALES
    # Se calcula a qué se dedica la potencia de cada renovable en cada hora (carga, surplus, bomba...)
    PERCENTAGE_RENEWABLES_PARAMS = pd.read_sql(
            "SELECT IdParameter, Type FROM AllocationParameters WHERE ParameterType = 'sunburstChildData'", GenericCode.engine)
    
    def __init__(self):
        # Constants?
        self._PCI_METHANE = 8.059
        self._VOL_METHANE_DIV_VOL_BIOGAS = 0.6
        self._ENGINE_EFFICIENCY = 0.29
        self.PBIO_DIV_CONS = 1 / self.ENGINE_EFFICIENCY / \
            self.PCI_METHANE / self.VOL_METHANE_DIV_VOL_BIOGAS
        self.constant_qbiogas = 0.07415
        self.constant_qbiomet = 0.6

        # Biogas variables
        self.digester_volume = 1400  # m3(cubic meters)
        self.generator_max_power = 150  # kW
        self.generator_min_power = 75  # kW
        self.gas_initial_volume = 12  # m3(cubic meters)
        self.biogas_maximum_volume = 0.4*self.digester_volume  # V
        self.biogas_minimum_volume = self.biogas_maximum_volume / 20  # V
        self.biogas_coefficient = 1

        # Biogas costs
        self.bio_kw_installation_cost = 6200  # €/kW
        self.bio_installation_cost = self.generator_max_power * \
            self.bio_kw_installation_cost  # €
        self.bio_generation_mean_cost = 25  # cents/kWh
        self.bio_amortization_period = 12  # Years

        # Photovoltaic variables
        self.photovoltaic_power = 150  # kW
        self.max_demand = 500
        self.pvFarmsInstalledPower = 200  # kW
        # PV Costs
        self.pv_kw_installation_cost = 1210  # €/kW
        self.pv_installation_cost = self.photovoltaic_power * \
            self.pv_kw_installation_cost  # €
        self.pv_generation_mean_cost = 4.5  # cents/kWh
        self.pv_amortization_period = 12  # Years

        # Eolic variables
        self.wind_turbine_power = 100  # kW
        self.min_speed = 5  # km/h
        self.max_speed = 15  # km/h
        self.max_speed_limit = 24  # km/h
        # Eolic Costs
        self.eol_kw_installation_cost = 1700  # €/kW
        self.eol_installation_cost = self.wind_turbine_power * \
            self.eol_kw_installation_cost  # €
        self.eol_generation_mean_cost = 5.45  # cents/kWh
        self.eol_amortization_period = 12  # Years

        # Acuatic variables?
        self._upper_tank_volume = 12000  # m3(cubic meters)
        self.lower_tank_volume = 12000  # m3(cubic meters)
        self._initial_upper_tank_volume = 12000  # m3(cubic meters)
        self.initial_lower_tank_volume = 0  # m3(cubic meters)

        self.lower_maximum_volume_dam = self._upper_tank_volume - \
            self._initial_upper_tank_volume  # m3(cubic meters)

        self.turbine_power = 150  # kW/h
        self.pump_power = 150  # kW/h
        self._performance = 0.8
        self._hydraulic_jump = 160  # m
        self.Qg_presa = 1/9.81/self.hydraulic_jump/self.performance*3600
        self.Qb_presa = 1/9.81/self.hydraulic_jump*3600*self.performance

        # Acuatic costs
        self.hydraulic_kw_installation_cost = 1620  # €/kW
        self.hydraulic_deposit_installation_cost = 24.35  # €/m3
        self.hydraulic_installation_cost = ((self.turbine_power + self.pump_power) * self.hydraulic_kw_installation_cost + (
            self.lower_tank_volume + self.upper_tank_volume)*self.hydraulic_deposit_installation_cost)*1.5  # €
        self.hydraulic_generation_mean_cost = 4.5  # cents/kWh
        self.hydraulic_amortization_period = 12  # Years

        # Exponential and Rayleigh
        self.pvExponentialScale = 4380
        self.pvExponentialSize = 1
        self.pvRayleighScale = 24
        self.pvRayleighSize = 1
        self.windPowerExponentialScale = 4380
        self.windPowerExponentialSize = 1
        self.windPowerRayleighScale = 24
        self.windPowerRayleighSize = 1
        self.biogasExponentialScale = 4380
        self.biogasExponentialSize = 1
        self.biogasRayleighScale = 24
        self.biogasRayleighSize = 1
        self.hydraulicExponentialScale = 4380
        self.hydraulicExponentialSize = 1
        self.hydraulicRayleighScale = 24
        self.hydraulicRayleighSize = 1

        self.setRenewableCosts()

    def setRenewableCosts(self):
        dayHours = 365*24
        self.bio_amortization_cost_hour = self.bio_installation_cost / \
            (self.bio_amortization_period*dayHours)
        self.pv_amortization_cost_hour = self.pv_installation_cost / \
            (self.pv_amortization_period*dayHours)
        self.eol_amortization_cost_hour = self.eol_installation_cost / \
            (self.eol_amortization_period*dayHours)
        self.hydraulic_amortization_cost_hour = self.hydraulic_installation_cost / \
            (self.hydraulic_amortization_period*dayHours)

    # Returns a dataframe with the simulation for a whole year starting from a given date, a database connection needs to be passed
    def range_simulation(self, start_day="2022-12-01", end_day="2023-01-01", location={}, parameters={}, demandSelected='Power', with_failures=True):
        current_date = dt.datetime.strptime(start_day, "%Y-%m-%d")
        final_date = dt.datetime.strptime(end_day, "%Y-%m-%d")
        (FV_hours_until_failure, Eolic_hours_until_failure, Biogas_hours_until_failure, Turbine_hours_until_failure, Pump_hours_until_failure,
         general_table, next_hours) = self.initializeVariables(with_failures, final_date, current_date, location['Area'])

        while current_date <= final_date:
            (FV_hours_until_failure, Eolic_hours_until_failure, Biogas_hours_until_failure, Turbine_hours_until_failure, Pump_hours_until_failure,
                 next_hours) = self.initializeFailures(with_failures, FV_hours_until_failure, Eolic_hours_until_failure, Biogas_hours_until_failure,
                                                       Turbine_hours_until_failure, Pump_hours_until_failure, next_hours)
            try:
                general_table = pd.concat([general_table, self.getDailyAssignmentHistorical(objective_date=current_date.strftime("%Y-%m-%d"),
                                                                                                location=location, previous_day=general_table,
                                                                                                demandSelected=demandSelected, failures=next_hours,
                                                                                                parameters=parameters)], ignore_index=True)
            except Exception as e:
                print(f"Error en: {current_date}", e)
                
            current_date = current_date + dt.timedelta(days=1)

        return general_table

    def initializeVariables(self, with_failures, final_date, current_date, area, locationGenerator=None):
        self.setRenewableCosts()
        self.qBiogasGenerado = self.constant_qbiogas * \
            self.digester_volume * (self.biogas_generation_percentage/100)
        self.qBiometGenerado = self.qBiogasGenerado * 0.6
        # Se calcula la potencia total dependiendo de las granjas. Si se está en predicción, solo la del recurso seleccionado,
        # y si se está en el histórico, de todas las granjas del área
        farmsQuery = f"SELECT * FROM Locations WHERE Area = {area} AND Type = 'Generator'"
        if locationGenerator:
            farmsQuery += f'AND id = {locationGenerator}'
        farms = pd.read_sql(farmsQuery, GenericCode.engine)
        farmsPV = farms[farms['ResourceType'] == 'photovoltaic']
        self.pvFarmsInstalledPower = farmsPV['InstalledPower'].sum()
        FV_hours_until_failure = []
        Eolic_hours_until_failure = []
        Biogas_hours_until_failure = []
        Turbine_hours_until_failure = []
        Pump_hours_until_failure = []
        # If want simulate with failures...
        if with_failures == True:
            # Start variables
            hours_total_number = (final_date-current_date).days * 24
            # Loading hours until failures on each variable. It works like a FIFO queue
            while len(FV_hours_until_failure) <= hours_total_number or len(Eolic_hours_until_failure) <= hours_total_number or len(Biogas_hours_until_failure) <= hours_total_number or len(Turbine_hours_until_failure) <= hours_total_number or len(Pump_hours_until_failure) <= hours_total_number:
                # CHANGE Better memory usage
                if len(FV_hours_until_failure) <= hours_total_number:
                    FV_hours_until_failure += ([1] * self.generate_exponential(self.pvExponentialScale, self.pvExponentialSize)[
                                               0]) + ([0] * self.generate_rayleigh(self.pvRayleighScale, self.pvRayleighSize)[0])
                if len(Eolic_hours_until_failure) <= hours_total_number:
                    Eolic_hours_until_failure += ([1] * self.generate_exponential(self.windPowerExponentialScale, self.windPowerExponentialSize)[
                                                  0]) + ([0] * self.generate_rayleigh(self.windPowerRayleighScale, self.windPowerRayleighSize)[0])
                if len(Biogas_hours_until_failure) <= hours_total_number:
                    Biogas_hours_until_failure += ([1] * self.generate_exponential(self.biogasExponentialScale, self.biogasExponentialSize)[
                                                   0]) + ([0] * self.generate_rayleigh(self.biogasRayleighScale, self.biogasRayleighSize)[0])
                if len(Turbine_hours_until_failure) <= hours_total_number:
                    Turbine_hours_until_failure += ([1] * self.generate_exponential(self.hydraulicExponentialScale, self.hydraulicExponentialSize)[
                                                    0]) + ([0] * self.generate_rayleigh(self.hydraulicRayleighScale, self.hydraulicRayleighSize)[0])
                if len(Pump_hours_until_failure) <= hours_total_number:
                    Pump_hours_until_failure += ([1] * self.generate_exponential(self.hydraulicExponentialScale, self.hydraulicExponentialSize)[
                        0]) + ([0] * self.generate_rayleigh(self.hydraulicRayleighScale, self.hydraulicRayleighSize)[0])

        general_table = None
        next_hours = None

        return (FV_hours_until_failure, Eolic_hours_until_failure, Biogas_hours_until_failure, Turbine_hours_until_failure, Pump_hours_until_failure,
                general_table, next_hours)

    def initializeFailures(self, with_failures, FV_hours_until_failure, Eolic_hours_until_failure, Biogas_hours_until_failure,
                           Turbine_hours_until_failure, Pump_hours_until_failure, next_hours):
        if with_failures == True:
            # shifting/poping 24 the first 24 hours of each variable
            next_hours = {"fv_working": [], "eolic_working": [
            ], "biogas_working": [], "turbine_working": [], "pump_working": []}
            FV_hours_until_failure, Eolic_hours_until_failure, Biogas_hours_until_failure, Turbine_hours_until_failure, Pump_hours_until_failure = self.shift_lists(
                FV_hours_until_failure, Eolic_hours_until_failure, Biogas_hours_until_failure, Turbine_hours_until_failure, Pump_hours_until_failure)
            # Index 0 = failures of the current day, index 1 = FIFO queue without the first 24 values (queue[24:])
            next_hours["fv_working"], FV_hours_until_failure = FV_hours_until_failure[0], FV_hours_until_failure[1]
            next_hours["eolic_working"], Eolic_hours_until_failure = Eolic_hours_until_failure[0], Eolic_hours_until_failure[1]
            next_hours["biogas_working"], Biogas_hours_until_failure = Biogas_hours_until_failure[0], Biogas_hours_until_failure[1]
            next_hours["turbine_working"], Turbine_hours_until_failure = Turbine_hours_until_failure[0], Turbine_hours_until_failure[1]
            next_hours["pump_working"], Pump_hours_until_failure = Pump_hours_until_failure[0], Pump_hours_until_failure[1]

        return (FV_hours_until_failure, Eolic_hours_until_failure, Biogas_hours_until_failure, Turbine_hours_until_failure, Pump_hours_until_failure, next_hours)

    # Returns a dataframe with the simulation for the target day, a database connection needs to be passed

    def getDailyAssignmentHistorical(self, objective_date="2021-12-31", location={}, previous_day=None,
                                     demandSelected='Power', failures=None, parameters={}):
        objective_date = parser.parse(objective_date)
        day_data = pd.read_sql(f"""SELECT d.Hour, CONVERT(varchar(10), d.Date, 23) AS Fecha,
                               h.windspeed_10m,h.temperature_2m, d.Date,g.{demandSelected} AS Power, e.Price, e.Surplus
                               FROM datosGEDER2 g, HistoricalWeather h, Dates d, Locations l, ElectricityPrice e
                               WHERE e.date=d.id and l.Area = h.Area and g.date = d.id
                               and d.id = h.date and l.id ={location['Location']}
                               and g.location = {location['Location']} and d.Year = {objective_date.year}
                               and d.Month={objective_date.month} and d.Day={objective_date.day}
                               ORDER BY CONCAT(Year,'-',Month,'-',Day), d.Hour """, GenericCode.engine)
        # FETCHING PHOTOVOLTAIC GENERATION DATA FROM ALL FARMS
        generation_of_day = pd.read_sql(f"""SELECT l.Name, d.Hour, CONVERT(varchar(10), d.Date, 23) as Fecha,
                                        h.windspeed_10m, d.Date,g.Power FROM datosGEDER2 g, HistoricalWeather h, Dates d, Locations l
                                        WHERE l.Area = h.Area and g.date = d.id and d.id = h.date and l.id = g.location
                                        and l.Area = {location['Area']} and l.Type = 'Generator'
                                        and d.Year = {objective_date.year} and d.Month = {objective_date.month} and d.Day = {objective_date.day}
                                        ORDER BY l.name, CONCAT(Year,'-',Month,'-',Day), d.Hour """, GenericCode.engine)

        return self.getDailyAssignment(day_data, generation_of_day, objective_date, previous_day, failures, parameters)

    # Returns a dataframe with the simulation for the target day, a database connection needs to be passed
    def getDailyAssignment(self, day_data, generation_of_day, objective_date, previous_day=None, failures=None, parameters={}):
        generation_by_hour = abs(generation_of_day.groupby(
            by=["Hour"]).sum(numeric_only=True)["Power"])
        aux_table = []
        for hour in range(0, 24):
            # Add date to row
            date = objective_date + dt.timedelta(hours=hour)
            date = date.strftime('%Y-%m-%d %H:%M')

            if hour == 0 and previous_day is not None:
                # Se llama al método pasando la última hora del día anterior
                previous_hour = self.get_hour_assignment(date=date, hour=hour, day_data=day_data, generation_by_hour=generation_by_hour,
                                                         previous_hour=previous_day.iloc[-1].to_dict(), failures=failures, parameters=parameters)
                aux_table.append(previous_hour)
            elif hour == 0 and previous_day is None:
                previous_hour = self.get_hour_assignment(
                    date=date, hour=hour, day_data=day_data, generation_by_hour=generation_by_hour, previous_hour=[], failures=failures, parameters=parameters)
                aux_table.append(previous_hour)
            else:
                previous_hour = self.get_hour_assignment(
                    date=date, hour=hour, day_data=day_data, generation_by_hour=generation_by_hour, previous_hour=previous_hour, failures=failures, parameters=parameters)
                aux_table.append(previous_hour)
                # aux_table = pd.concat(
                #     [aux_table, previous_hour, ], ignore_index=True)

        # La potencia de Bombeo debe de ir en negativo
        table_df = pd.DataFrame(aux_table)

        table_df['PotBombeo2Modified'] = -table_df['PotBombeo2Modified']
        table_df['PotBombeo2'] = -table_df['PotBombeo2']

        return table_df

    def get_hour_assignment(self, hour, date, previous_hour, day_data, generation_by_hour, failures, parameters={}, repeated=False):
        table = {"Date": None, "Hour": None, "FV working": None,  "Eolic working": None, "PotDem": None, "Biogas working": None, "Pump working": None,
                 "Turbine working": None, "ElectricityGridPrice": None, "ElectricitySurplusPrice": None, "FV coefficient": None, "Eolic coefficient": None,
                 "Biogas coefficient": None, "FVGenerationCostModified": None, "FVCostModified": None, "EolGenerationCostModified": None, "EolCostModified": None,
                 'VolBioInicialModified': None, 'PotBio2Modified': None, "BioGenerationCostModified": None, "BioCostModified": None, "SOSVolBioFinalModified": None,
                 'PotDem2Modified': None, 'PotBombeoModified': None, 'PotTurbinaModified': None, 'VolDepInf1Modified': None, 'VolDepSup1Modified': None,
                 "HydraulicGenerationCostModified": None, "HydraulicCostModified": None, "SOSVolDepSup2Modified": None, 'RenewablesPowerModified': None,
                 'PotDemFinalModified': None, "MoneySpentModified": None, 'DifferenceWithourGridModified': None, "nF FV": None, "nF Eolic": None,
                 "nF Bio": None, "nF Pump": None, "nF Turbine": None}

        for parameter in parameters:
            table[parameter] = None

        if failures is not None:
            table["FV working"] = (failures["fv_working"][hour])
            table["Eolic working"] = (failures["eolic_working"][hour])
            table["Biogas working"] = (failures["biogas_working"][hour])
            table["Pump working"] = (failures["turbine_working"][hour])
            table["Turbine working"] = (failures["pump_working"][hour])
        else:
            table["FV working"] = 1
            table["Eolic working"] = 1
            table["Biogas working"] = 1
            table["Pump working"] = 1
            table["Turbine working"] = 1

        # CHANGE NUMBER OF FAILURES
        if failures is None:
            table["nF FV"] = 0
            table["nF Eolic"] = 0
            table["nF Bio"] = 0
            table["nF Pump"] = 0
            table["nF Turbine"] = 0
        elif len(previous_hour) == 0:
            # If any table["* working"] = 1(working, not failure) then 0 (1-1=0)
            table["nF FV"] = 1 - table["FV working"]
            table["nF Eolic"] = 1 - table["Eolic working"]
            table["nF Bio"] = 1 - table["Biogas working"]
            table["nF Pump"] = 1 - table["Pump working"]
            table["nF Turbine"] = 1 - table["Turbine working"]
        else:
            table["nF FV"] = 1 if table["FV working"] < previous_hour["FV working"] else 0
            table["nF Eolic"] = 1 if table["Eolic working"] < previous_hour["Eolic working"] else 0
            table["nF Bio"] = 1 if table["Biogas working"] < previous_hour["Biogas working"] else 0
            table["nF Pump"] = 1 if table["Pump working"] < previous_hour["Pump working"] else 0
            table["nF Turbine"] = 1 if table["Turbine working"] < previous_hour["Turbine working"] else 0

        # Add date to row
        table["Date"] = (date)
        table["Hour"] = (hour)

        # Se calcula el precio de la electricidad del día actual
        table["ElectricityGridPrice"] = day_data["Price"].values[hour] / 1000
        surplus_price = 0.93 * \
            (day_data["Surplus"].values[hour] / 1000) - (0.5/1000)
        # Divide by 1000 because Price is in Eu/MWh
        table["ElectricitySurplusPrice"] = (surplus_price)
        
        table['QBiogasGenerado'] = self.qBiogasGenerado
        table['QBiometGenerado'] = self.qBiometGenerado

        # If there are missing hours in the day, we cannot calculate the subsequent hours
        try:
            # Add the corresponding photovoltaic power for the hour
            table["PotFVUni"] = (
                (generation_by_hour.values[hour]/self.pvFarmsInstalledPower) * table["FV working"])
        except:
            raise

        # Add the corresponding wind speed for the hour and calculate the generated power as a percentage of the installed power
        table["VelViento"] = (day_data["windspeed_10m"].values[hour])
        table["Temperature"] = (day_data["temperature_2m"].values[hour])

        if table["VelViento"] < self.min_speed or table["VelViento"] >= self.max_speed_limit:
            result = 0
        elif table["VelViento"] > self.max_speed and table["VelViento"] < self.max_speed_limit:
            result = 1
        else:
            result = (table["VelViento"] - self.min_speed) / \
                (self.max_speed - self.min_speed)

        table["PotEolUni"] = (result * table["Eolic working"])
        # Add the corresponding consumed power for the hour (percentage with respect to scaling factor (maximum demanded power))
        table["PotDemUni"] = (
            day_data["Power"].values[hour] / GenericCode.MAX_DEMAND)

        table["PotDem"] = (table["PotDemUni"] * self.max_demand)
        table["EnergyCostWithoutRenewables"] = table["PotDem"] * \
            table["ElectricityGridPrice"]

        modified = ''
        if repeated:
            modified = 'Modified'

        table = self.setPvAndWindPower(modified, table)

        # If it hasn't been met (table["PotDem1"][hour] > 0), calculate the generation with biogas as accurately or as maximally as possible
        p_bio_1 = 0
        if table["PotDem1" + modified] > 0:
            p_bio_1 = min(table["PotDem1" + modified],
                          self.generator_max_power)

        table["PotBio1"] = (p_bio_1 * table["Biogas working"])

        table = self.setBiogasAndHydraulic(
            modified, table, previous_hour)

        if not repeated:
            table = self.setCommonRenewableData(modified, table, previous_hour)

        # default values
        table["FV coefficient"] = 1
        table["Eolic coefficient"] = 1
        table["Biogas coefficient"] = 1

        # Start the management (turning off things) only if the power is less than 0
        # 'Repeated' is used to control recursion
        modified = 'Modified'
        if not repeated and round(table["PotDemFinal"], 3) < 0:
            best = [1, 1, round(table["PotDemFinal"], 3), 1]
            original_fv = self.photovoltaic_power
            original_eolic = self.wind_turbine_power
            # original_biogas = self.generator_max_power # esto ya no se usa
            better = False

            self.biogas_coefficient = 0.75
            # self.generator_max_power = self.generator_max_power * self.biogas_coefficient
            result = self.get_hour_assignment(
                hour, date, previous_hour, day_data, generation_by_hour, failures, repeated=True)

            # Si demanda final superior o igual a 0 con 0.75 entonces no podemos apagar biogas, calculamos siguiente hora
            if round(result["PotDemFinalModified"], 3) >= 0:
                self.biogas_coefficient = 1
            else:
                # Si no se cumple lo anterior tenemos nuevo mejor resultado con coeficiente 0.75,
                best = [1, 1, round(result["PotDemFinalModified"], 3),
                        self.biogas_coefficient]
                # Ahora miramos coeficiente de 0.5
                self.biogas_coefficient = 0.5
                result = self.get_hour_assignment(
                    hour, date, previous_hour, day_data, generation_by_hour, failures, repeated=True)
                if round(result["PotDemFinalModified"], 3) >= 0:
                    self.biogas_coefficient = 0.75
                else:
                    best = [1, 1, round(
                        result["PotDemFinalModified"], 3), self.biogas_coefficient]

            # Se baja el biogas al 25% para comprobar si sigue habiendo excedente
            if self.biogas_coefficient == 0.5:
                self.biogas_coefficient = 0.25
                result = self.get_hour_assignment(
                    hour, date, previous_hour, day_data, generation_by_hour, failures, repeated=True)

                # Si demanda final superior o igual a 0 con 0.25 entonces no podemos apagar biogas, calculamos siguiente hora
                if round(result["PotDemFinalModified"], 3) >= 0:
                    self.biogas_coefficient = 0.5
                else:
                    # Si no se cumple lo anterior tenemos nuevo mejor resultado con coeficiente 0.25,
                    best = [1, 1, round(result["PotDemFinalModified"], 3),
                            self.biogas_coefficient]

            if self.biogas_coefficient == 0.25:
                for coefficient_FV in [0, 0.25, 0.5, 0.75, 1]:
                    self.photovoltaic_power = self.photovoltaic_power * coefficient_FV
                    for coeficcient_Eol in [0, 0.25, 0.5, 0.75, 1]:
                        self.wind_turbine_power = self.wind_turbine_power * coeficcient_Eol
                        result = self.get_hour_assignment(
                            hour, date, previous_hour, day_data, generation_by_hour, failures, repeated=True)
                        if (round(result["PotDemFinalModified"], 3) >= best[2] and round(result["PotDemFinalModified"], 3) <= 0 and
                                result["PotBombeo2Modified"] >= 0.8 * table["PotBombeo2"]):
                            best = [coefficient_FV, coeficcient_Eol, round(
                                result["PotDemFinalModified"], 3), self.biogas_coefficient]
                            better = True
                            self.wind_turbine_power = original_eolic
                            break
                        self.wind_turbine_power = original_eolic
                    self.photovoltaic_power = original_fv
                    if better:
                        break
            else:
                result = self.get_hour_assignment(
                    hour, date, previous_hour, day_data, generation_by_hour, failures, repeated=True)
                best = [1, 1, round(result["PotDemFinalModified"], 3),
                        self.biogas_coefficient]

            table.update(result)
            table["FV coefficient"] = best[0]
            table["Eolic coefficient"] = best[1]
            table["Biogas coefficient"] = best[3]
            table["PotDemFinalModified"] = best[2]
            # Devolvemos max power a su valor original. ESTO YA NO HACE FALTA PERO LO DEJO POR SI ACASO
            # self.generator_max_power = original_biogas
            self.biogas_coefficient = 1

        elif not repeated:
            table = self.setPvAndWindPower(modified, table)
            table = self.setBiogasAndHydraulic(modified, table, previous_hour)

        if not repeated:
            table = self.setCommonRenewableData(modified, table, previous_hour)

        return table

    def roundNumber(value):
        return round(value, 2)

    # CHANGE SUMMARY
    def get_summary(dataframe=None, optimize=False,  csv_filename=None):
        if dataframe is not None:
            table = dataframe
        else:
            table = pd.read_csv(csv_filename, decimal=",", sep=";")
        summary = []
        # Hay 2 sumarios, el normal y el modificado/gestionado
        for i in ("", "Modified"):
            renewableData = {}

            renewableData["surplusSummary"] = GenericCode.roundNumber(
                table["Surplus"+i].sum())
            renewableData["gridSummary"] = GenericCode.roundNumber(
                table["Grid"+i].sum())
            absoluteSurplus = abs(renewableData["surplusSummary"])
            renewableData["balance"] = GenericCode.roundNumber(
                renewableData["gridSummary"] + renewableData["surplusSummary"])
            renewableData["absoluteSum"+i] = GenericCode.roundNumber(renewableData["surplusSummary"] +
                                                                     renewableData["gridSummary"])
            renewableData["interchangeCount"] = len(table.query(
                f"`Grid{i}` != 0 |`Surplus{i}` != 0 ")["Hour"])
            renewableData["numberFailures"] = table["nF FV"].sum() + table["nF Eolic"].sum(
            ) + table["nF Bio"].sum() + table["nF Pump"].sum() + table["nF Turbine"].sum()
            renewableData["sosWaterTank"] = GenericCode.roundNumber(
                table["SOSVolDepSup2"+i].mean())
            renewableData["sosBiogas"] = GenericCode.roundNumber(
                table["SOSVolBioFinal"+i].mean())
            renewableData["loleSin"] = table["LOLESin"+i].sum()
            renewableData["loleCon"] = table["LOLECon"+i].sum()
            renewableData["loleTotal"] = GenericCode.roundNumber(renewableData["loleCon"] +
                                                                 renewableData["loleSin"])
            num_hours = len(table)
            renewableData["lolpSin"] = GenericCode.roundNumber(
                renewableData["loleSin"] / num_hours * 100)
            renewableData["lolpCon"] = GenericCode.roundNumber(
                renewableData["loleCon"] / num_hours * 100)
            renewableData["lolpTotal"] = GenericCode.roundNumber(renewableData["lolpSin"] +
                                                                 renewableData["lolpCon"])
            renewableData["lossLoad"] = renewableData["gridSummary"]
            renewableData["energyNotUsed"] = GenericCode.roundNumber(
                absoluteSurplus + table['PotQuemAnt'+i].sum())
            renewableData["energyCostRenewables"] = GenericCode.roundNumber(
                table['EnergyCostWithRenewables'+i].sum())
            renewableData["energyInterchange"] = GenericCode.roundNumber(
                abs(renewableData["gridSummary"]) + absoluteSurplus)

            if not optimize:
                renewableData["numberInterruptions"] = table["nIDG"+i].sum()
                renewableData['Simulation'] = 'Without Regulation'
                if i == 'Modified':
                    renewableData['Simulation'] = 'With Regulation'

            summary.append(renewableData)

        return summary

    def generate_exponential(self, scale, size):
        # 2 fallos/año = 1 fallo cada 0.5 años = 1 fallo cada 0.5*365 días = 182.5 días = 4380 horas
        random_numbers = np.random.exponential(scale=scale, size=size)
        number_list = list(map(lambda x: int(x), random_numbers))
        return number_list

    def generate_rayleigh(self, scale, size):
        random_numbers = np.random.rayleigh(scale=scale, size=size)
        number_list = list(map(lambda x: int(x), random_numbers))
        return number_list

    def shift_lists(self, *listas):
        shifted_lists = []
        for lista in listas:
            shifted_lists.append((lista[:24], lista[24:]))
        return tuple(shifted_lists)

    def setPvAndWindPower(self, modified, table):
        # pasa algo raro float * float devuelve INT??? en la calculadora de windows también da un int con los mismos datos pero en el excel no *SOLUCIONADO, pero lo dejo aqui por si acaso*
        table["PotFV" +
              modified] = float(table["PotFVUni"] * self.photovoltaic_power)
        # Calculate wind generation
        table["PotEol" + modified] = table["PotEolUni"] * \
            self.wind_turbine_power

        table["PotDem1" + modified] = table["PotDem"] - \
            table["PotFV" + modified] - table["PotEol" + modified]

        return table

    def setBiogasAndHydraulic(self, modified, table, previous_hour):
        if len(previous_hour) != 0:
            table['VolBioInicial' + modified] = (previous_hour['VolBioFinal' + modified] -
                                                 table['PotBio1'] * self.PBIO_DIV_CONS + self.qBiogasGenerado)

        else:
            table["VolBioInicial" + modified] = (
                self.gas_initial_volume - table["PotBio1"] * self.PBIO_DIV_CONS + self.qBiogasGenerado)

        if table['VolBioInicial' + modified] > self.biogas_maximum_volume:
            result = table['PotBio1'] + (table['VolBioInicial' + modified]
                                         - self.biogas_maximum_volume) / self.PBIO_DIV_CONS
        elif table['VolBioInicial' + modified] > self.biogas_minimum_volume:
            result = table['PotBio1']
        else:
            result = table['PotBio1'] - (
                self.biogas_minimum_volume - table['VolBioInicial' + modified]) / self.PBIO_DIV_CONS
        table['PotBio2' + modified] = result
        # Biogas Power Modified
        table['PotBio3' + modified] = (min(
            self.biogas_coefficient * self.generator_max_power, table['PotBio2' + modified] * self.biogas_coefficient))

        table['PotDem2' + modified] = table['PotDem1' + modified] - \
            table['PotBio3' + modified]

        if table['PotDem2' + modified] >= 0:
            result = 0
        elif -table['PotDem2' + modified] < self.pump_power:
            result = -table['PotDem2' + modified]
        else:
            result = self.pump_power

        table['PotBombeo' + modified] = (
            result * table['Pump working'])

        result = 0
        if table['PotDem2' + modified] > 0:
            result = min(self.turbine_power,
                         table['PotDem2' + modified])

        table['PotTurbina' + modified] = result * table['Turbine working']

        if len(previous_hour) != 0:
            table['VolDepInf1' + modified] = (previous_hour['VolDepInf2' + modified] + table['PotTurbina' + modified] * self.Qg_presa
                                              - table['PotBombeo' + modified] * self.Qb_presa)
            table['VolDepSup1' + modified] = (previous_hour['VolDepSup2' + modified] - table['PotTurbina' + modified] * self.Qg_presa
                                              + table['PotBombeo' + modified]*self.Qb_presa)

        else:
            table["VolDepInf1" + modified] = (min(self.lower_maximum_volume_dam, self.initial_lower_tank_volume) +
                                              table["PotTurbina" + modified] * self.Qg_presa - table["PotBombeo" + modified] * self.Qb_presa)
            table["VolDepSup1" + modified] = (self.initial_upper_tank_volume - table["PotTurbina" + modified] * self.Qg_presa
                                              + table["PotBombeo" + modified]*self.Qb_presa)

        if table['VolDepInf1' + modified] <= 0:
            if len(previous_hour) != 0:
                result = previous_hour['VolDepInf2' + modified] / self.Qb_presa
            else:
                result = self.initial_lower_tank_volume/self.Qb_presa

        elif table['VolDepSup1' + modified] > self.upper_tank_volume:
            result = table['PotBombeo' + modified] - \
                (table['VolDepSup1' + modified] -
                 self.upper_tank_volume) / self.Qb_presa

        else:
            result = table['PotBombeo' + modified]

        table['PotBombeo2' + modified] = (round(result, 4))

        if table['VolDepSup1' + modified] <= 0:
            if len(previous_hour) != 0:
                result = previous_hour['VolDepSup2' + modified] / self.Qg_presa
            else:
                result = self.initial_upper_tank_volume/self.Qg_presa

        elif table['VolDepInf1' + modified] > self.lower_tank_volume:
            result = table['PotTurbina' + modified] - \
                (table['VolDepInf1' + modified] -
                 self.lower_tank_volume) / self.Qg_presa

        else:
            result = table['PotTurbina' + modified]

        table['PotTurbina2' + modified] = (result)

        table['PotDemFinal' + modified] = table['PotDem2' + modified] - \
            table['PotTurbina2' + modified] + table['PotBombeo2' + modified]

        return table

    def setCommonRenewableData(self, modified, table, previous_hour):
        if len(previous_hour) != 0:
            table['VolBioFinal' + modified] = (previous_hour['VolBioFinal' + modified] -
                                               table['PotBio2' + modified] * self.PBIO_DIV_CONS + self.qBiogasGenerado)
            table['VolDepInf2' + modified] = (previous_hour['VolDepInf2' + modified] + table['PotTurbina2' + modified] * self.Qg_presa
                                              - table['PotBombeo2' + modified] * self.Qb_presa)
            table['VolDepSup2' + modified] = (previous_hour['VolDepSup2' + modified] - table['PotTurbina2' + modified] * self.Qg_presa +
                                              table['PotBombeo2' + modified] * self.Qb_presa)

        else:
            table['VolBioFinal' + modified] = (
                self.gas_initial_volume - table['PotBio3' + modified] * self.PBIO_DIV_CONS + self.qBiogasGenerado)
            table['VolDepInf2' + modified] = (min(self.lower_maximum_volume_dam, self.initial_lower_tank_volume) +
                                              table['PotTurbina2' + modified] * self.Qg_presa - table['PotBombeo2' + modified] * self.Qb_presa)
            table['VolDepSup2' + modified] = (self.initial_upper_tank_volume - table['PotTurbina2' + modified] * self.Qg_presa +
                                              table['PotBombeo2' + modified] * self.Qb_presa)

        table["FVGenerationCost" + modified] = table["PotFV" + modified] * \
            (self.pv_generation_mean_cost / 100)
        table["FVCost" + modified] = table["FVGenerationCost" +
                                           modified] + self.pv_amortization_cost_hour

        table["EolGenerationCost" + modified] = table["PotEol" + modified] * \
            (self.eol_generation_mean_cost / 100)
        table["EolCost" + modified] = table["EolGenerationCost" +
                                            modified] + self.eol_amortization_cost_hour

        table["BioGenerationCost" + modified] = (
            table["PotBio3" + modified] * (self.bio_generation_mean_cost / 100))
        table["BioCost" + modified] = (
            table["BioGenerationCost" + modified] + self.bio_amortization_cost_hour)
        # Quemado en antorcha
        table['PotQuemAnt' + modified] = table['PotBio2' +
                                               modified] - table['PotBio3' + modified]
        # Se calcula el porcentaje de quema en antorcha, comparado con el máximo que se puede quemar
        table['SoSPotQuemAnt' +
              modified] = (table['PotQuemAnt' + modified]/self.biogas_max_digester) * 100

        # CHANGE % of Digester volume available  SOS = State of Storage
        if self.digester_volume != 0:
            table['SOSVolBioFinal' + modified] = GenericCode.roundNumber(((table['VolBioFinal' + modified]-self.biogas_minimum_volume) / (
                self.biogas_maximum_volume-self.biogas_minimum_volume)) * 100)

        else:
            table['SOSVolBioFinal' + modified] = 0

        # CHANGE % of Upper tank volume available SOS = State of Storage
        table['SOSVolDepSup2' + modified] = GenericCode.roundNumber(table['VolDepSup2' + modified] /
                                                                    self.upper_tank_volume * 100)
        table["HydraulicGenerationCost" + modified] = table["PotTurbina2" +
                                                            modified] * (self.hydraulic_generation_mean_cost / 100)
        table["HydraulicCost" + modified] = table["HydraulicGenerationCost" +
                                                  modified] + self.hydraulic_amortization_cost_hour

        # Separation of "PotDemFinal" in Surplus and Grid
        if table['PotDemFinal' + modified] >= 0:
            table['Grid' + modified] = table['PotDemFinal' + modified]
            table['Surplus' + modified] = 0
        else:
            table['Grid' + modified] = 0
            table['Surplus' + modified] = table['PotDemFinal' + modified]

        table['MoneySpent' + modified] = (table['Grid' + modified] * (
            table['ElectricityGridPrice']) - table['Surplus' + modified] * (table['ElectricitySurplusPrice']))
        table['EnergyCostWithRenewables' + modified] = (
            table['MoneySpent' + modified] + table['FVCost' + modified] + table['EolCost' + modified] + table['BioCost' + modified] + table['HydraulicCost' + modified])
        table['DifferenceWithourGrid' + modified] = table['EnergyCostWithoutRenewables'] - \
            table['EnergyCostWithRenewables' + modified]
        table['RenewablesPower' + modified] = (table['PotFV' + modified] + table['PotEol' + modified] +
                                               table['PotBio3' + modified] + table['PotTurbina2' + modified])
        
        # Se calcula toda la potencia que se ha generado en cada hora
        table['RenewablesPowerWithGrid' + modified] = table['RenewablesPower' + modified] + table['Grid' + modified]
        table = self.getRenewablesPercentagePower(modified, table)

        if len(previous_hour) == 0 or not (round(previous_hour["PotDemFinal" + modified]) <= 0 and round(table["PotDemFinal" + modified]) > 0):
            table["nIDG" + modified] = 0
        else:
            table["nIDG" + modified] = 1

        # CHANGE COLUMN LOLE with failures
        table["LOLESin" + modified] = int(round(table["PotDemFinal" + modified]) > 0) * (table["FV working"] * table["Eolic working"]
                                                                                         * table["Biogas working"] * table["Pump working"]
                                                                                         * table["Turbine working"])
        table["LOLEAux" +
              modified] = int(round(table["PotDemFinal" + modified]) > 0)
        table["LOLECon" + modified] = table["LOLEAux" +
                                            modified] - table["LOLESin" + modified]

        return table
    
    def getRenewablesPercentagePower(self, modified, table):
        # Se agrupan por cada tipo de renovable
        for parentName, typeParams in simulator.PERCENTAGE_RENEWABLES_PARAMS.groupby('Type'):
            # Se calcula el porcentaje que corresponde a cada renovable de toda la generación (se incluye Grid)
            percentage = table[parentName + modified] / table['RenewablesPowerWithGrid' + modified]
            for index, typeParam in typeParams.iterrows():
                # En el ID se indica a qué se destina la potencia, separado por un guión la renovable a la que pertence
                percentageParam = typeParam['IdParameter'].split('-')[0]
                # La demanda siempre es la misma, surplus y bombeo cambia segun si hay regulación o no
                if percentageParam != 'PotDem':
                    percentageParam += modified
                table[typeParam['IdParameter'] + modified] = percentage * table[percentageParam]
        
        return table

    def getBiogasMinPower(parameter1):
        return parameter1 * 0.25
    
    def getBiogasGasInitialVolume(digesterVolume):
        return digesterVolume * 0.1

    def getInstallationCost(parameter1, parameter2):
        return parameter1 * parameter2

    def getWindPowerInstallationCost(parameter1, parameter2):
        return simulator.getInstallationCost(parameter1, parameter2)*1.5

    def getHydraulicInstallationCost(turbinePower, pumpPower, kWInstallationCost,
                                     upperTankVolume, lowerTankVolume, depositInstallationCost):
        powerInvestment = simulator.getInstallationCost(
            (turbinePower + pumpPower), kWInstallationCost)
        tanksInvestment = simulator.getInstallationCost(
            (upperTankVolume + lowerTankVolume), depositInstallationCost)

        return (powerInvestment + tanksInvestment) * 1.5

    def sameScenario(dic1, dic2):
        # Se comprueba si ese escenario ya está contemplado en un escenario anterior
        return all(dic1.get(key) == dic2.get(key) or dic1.get(key) == 0.0 for key in dic1)

    def keepScenario(scenario):
        # En caso de que se encuentren tanto potencia como volumen de biogas o hidráulica en el escenario,
        # deben cambiar el mismo porcentaje. En caso contrario, no se contempla el escenario
        biogasExists = 'generator_max_power' in scenario and 'digester_volume' in scenario
        hydraulicExists = 'hydraulic_power' in scenario and 'tank_volume' in scenario
        biogasEqualVolumeAndPower = biogasExists and scenario[
            'digester_volume'] == scenario['generator_max_power']
        hydraulicEqualVolumeAndPower = hydraulicExists and scenario[
            'hydraulic_power'] == scenario['tank_volume']

        return ((biogasEqualVolumeAndPower and not hydraulicExists) or
                (hydraulicEqualVolumeAndPower and not biogasExists) or
                (biogasEqualVolumeAndPower and hydraulicEqualVolumeAndPower) or
                (not biogasExists and not hydraulicExists))

    def optimizeParameters(self, optimizeParameters, originalValues, demandSelected, start_day="2022-12-01", end_day="2022-12-02",
                           location={}, simulationParameters={}, with_failures=True):
        scenarios = pd.read_sql(
            'SELECT * FROM OptimizationIntervals ORDER BY OptimizationOrder', GenericCode.engine)
        simulations = []
        scenariosIntervals = []
        totalLengthScenarios = 0
        GenericCode.executingOptimization = True
        GenericCode.stopOptimization = False
        # Se itera en todos los escenarios posibles (cambiando 1, 2, 3 o 4 recursos)
        for index, row in scenarios.iterrows():
            # Se seleccionan los parámetros que se van a cambiar
            scenarioParameters = row.loc[row.index.str.startswith(
                'Parameter')].dropna().values
            parametersIntervals = self.getParametersToChange(
                scenarioParameters, row)
            scenarioInterval = (self.getNewParameters(
                parametersIntervals, originalValues, scenarioParameters))
            for scenario in scenariosIntervals:
                scenarioInterval = [dic for dic in scenarioInterval if simulator.keepScenario(dic) and not any(simulator.sameScenario(dic, subdic)
                                                                                                               for subdic in scenario)]

            # Se añade el tamaño de cada escenario para obtener el tamaño total de los escenarios
            totalLengthScenarios += len(scenarioInterval)
            scenariosIntervals.append(scenarioInterval)

        index = 0
        for scenario in scenariosIntervals:
            # Se recuperan los valores originales antes de cada escenario
            for key, value in originalValues.items():
                setattr(self, key, value)

            scenarioParameters = scenario[0].keys()
            for combination in scenario:
                self.setSimulatorParameters(
                    scenarioParameters, originalValues, combination, optimizeParameters)
                simulationResult = self.range_simulation(
                    start_day, end_day, location, simulationParameters, demandSelected, with_failures)
                summary = simulator.get_summary(simulationResult, True)
                summary.append(
                    self.addResourceParameters(optimizeParameters['IdParameter']))
                simulations.append(summary)
                # Se añade a la cola el porcentaje de completitud de las simulaciones
                if GenericCode.progress_queue.empty():
                    optimizationPercentageCompleted = GenericCode.roundNumber(
                        100 * (index + 1) / totalLengthScenarios)
                    if optimizationPercentageCompleted < 100:
                        GenericCode.progress_queue.put(
                            optimizationPercentageCompleted)

                index += 1

                if GenericCode.stopOptimization:
                    GenericCode.waitQueueToBeEmpty()

                    GenericCode.progress_queue.put(0)
                    GenericCode.executingOptimization = False
                    exit(1)

        GenericCode.waitQueueToBeEmpty()
        GenericCode.progress_queue.put(100)
        GenericCode.waitQueueToBeEmpty()

        GenericCode.executingOptimization = False

        return simulations

    def addResourceParameters(self, scenarioParameters):
        return {parameter: GenericCode.roundNumber(getattr(self, parameter)) for parameter in scenarioParameters}

    def getNewParameters(self, parametersIntervals, originalValues, parameters):
        resourcesPossibleParameters = {}
        for parameter, intervals in parametersIntervals.items():
            interval = intervals['interval']
            jump = intervals['jump']
            actualValue = -interval
            resourcesPossibleParameters[parameter] = []
            while actualValue <= interval:
                resourcesPossibleParameters[parameter].append(actualValue)
                actualValue += jump

        combinations = []
        # Se obtienen todas las posibles combinaciones de los parámetros a modificar
        for combination in product(*resourcesPossibleParameters.values()):
            combinations.append(
                {parameter: interval for parameter, interval in zip(parameters, combination)})

        combinations = simulator.moveDefaultScenario(
            combinations, originalValues, parameters)

        return combinations

    def moveDefaultScenario(combinations, originalValues, optimizationParameters):
        # El escenario que corresponde con los datos originales se mueve a la primera posición
        for i, combination in enumerate(combinations):
            if all(combination[parameter] == 0.0 for parameter in optimizationParameters):
                # Se elimina los valores originales de las combinaciones, y se añade a la primera posición
                originalCombination = combinations.pop(i)
                combinations.insert(0, originalCombination)
                return combinations

        raise Exception('No se ha encontrado escenario por defecto')

    def setSimulatorParameters(self, parameters, originalValues, combination, optimizeParameters):
        for parameter in parameters:
            # Se obtienen las ids de los parámetros que cambian el mismo porcentaje (p.e. en biogas volumen digestor y gas inicial)
            simulatorParametersIds = optimizeParameters[optimizeParameters['IntervalParameter']
                                                        == parameter]['IdParameter']
            for simulatorParameter in simulatorParametersIds:
                setattr(self, simulatorParameter,
                        originalValues[simulatorParameter]*(1+combination[parameter]))

    def getParametersToChange(self, parameters, intervals):
        parametersIntervals = {}
        # Asigno a cada recurso su intervalo y salto
        for parameter in parameters:
            parametersIntervals[parameter] = {'interval': intervals[f'{parameter}_interval'],
                                              'jump': intervals[f'{parameter}_jump']}

        return parametersIntervals

    # VARIABLES QUE DEPENDEN DE OTRAS
    # Si volumen del reactor cambia el voltaje máximo y mínimo también
    @property
    def digester_volume(self):
        return self._digester_volume

    @digester_volume.setter
    def digester_volume(self, nuevo_valor):
        self._digester_volume = nuevo_valor
        self.biogas_maximum_volume = 0.4 * nuevo_valor
        self.biogas_minimum_volume = self.biogas_maximum_volume / 20  # V
        self.biogas_max_digester = (
            self.constant_qbiogas*nuevo_valor)/self.PBIO_DIV_CONS

    # Volumen maximo de la parte superior de la presa
    @property
    def upper_tank_volume(self):
        return self._upper_tank_volume

    @upper_tank_volume.setter
    def upper_tank_volume(self, nuevo_valor):
        self._upper_tank_volume = max(nuevo_valor, 1)
        self.initial_upper_tank_volume = min(
            self._upper_tank_volume, self.initial_upper_tank_volume)
        self.lower_maximum_volume_dam = self.upper_tank_volume - \
            self.initial_upper_tank_volume

    # Si hydraulic_jump cambia, Qg y Qb de presa también
    @property
    def hydraulic_jump(self):
        return self._hydraulic_jump

    @hydraulic_jump.setter
    def hydraulic_jump(self, nuevo_valor):
        self._hydraulic_jump = nuevo_valor
        self.Qg_presa = 1/9.81/nuevo_valor/self.performance*3600
        self.Qb_presa = 1/9.81/nuevo_valor*3600*self.performance

    # Si rendimiento de presa cambia, Qg y Qb de presa también
    @property
    def performance(self):
        return self._performance

    @performance.setter
    def performance(self, nuevo_valor):
        self._performance = nuevo_valor
        self.Qg_presa = 1/9.81/self.hydraulic_jump/nuevo_valor*3600
        self.Qb_presa = 1/9.81/self.hydraulic_jump*3600*nuevo_valor

    # Si algunas constantes cambian por algún motivo(que no deberían), PBIO_DIV_CONS debe cambiar
    @property
    def PCI_METHANE(self):
        return self._PCI_METHANE

    @PCI_METHANE.setter
    def PCI_METHANE(self, nuevo_valor):
        self._PCI_METHANE = nuevo_valor
        self.PBIO_DIV_CONS = 1 / self.ENGINE_EFFICIENCY / \
            nuevo_valor / self.VOL_METHANE_DIV_VOL_BIOGAS

    @property
    def VOL_METHANE_DIV_VOL_BIOGAS(self):
        return self._VOL_METHANE_DIV_VOL_BIOGAS

    @VOL_METHANE_DIV_VOL_BIOGAS.setter
    def VOL_METHANE_DIV_VOL_BIOGAS(self, nuevo_valor):
        self._VOL_METHANE_DIV_VOL_BIOGAS = nuevo_valor
        self.PBIO_DIV_CONS = 1 / self.ENGINE_EFFICIENCY / self.PCI_METHANE / nuevo_valor

    @property
    def ENGINE_EFFICIENCY(self):
        return self._ENGINE_EFFICIENCY

    @ENGINE_EFFICIENCY.setter
    def ENGINE_EFFICIENCY(self, nuevo_valor):
        self._ENGINE_EFFICIENCY = nuevo_valor
        self.PBIO_DIV_CONS = 1 / nuevo_valor / \
            self.PCI_METHANE / self.VOL_METHANE_DIV_VOL_BIOGAS
# simulador.range_simulation(engine=engine).to_csv("hola2.csv", mode='w', decimal=",", index=False,header=True ,sep=";",float_format='%.3f')
# last_day = simulador.get_daily_assignment(engine=engine).to_csv("hola2.csv", mode='w', decimal=",", index=False,header=True ,sep=";",float_format='%.3f')
