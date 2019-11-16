import requests
from bs4 import BeautifulSoup
import re
import json
import time
import os
import configparser
import sys


class WeatherCrawler(object):
    def __init__(self):
        # 检查下载文件夹目录结构
        self.__check_file_path()
        '''
            读取配置文件
        '''
        # 城市名称及对应编码
        self.city_code_dict = self.read_configs('city_code.ini', "CityCode")
        # 所有用到的URL
        self.base_urls = self.read_configs('china_weather.ini', "AllUrl")
        # 风向对应的编码
        self.wind_direction_code = self.read_configs('china_weather.ini', "WindDirectionCode")
        # 风速对应的编码
        self.wind_speed_code = self.read_configs('china_weather.ini', "WindSpeedCode")
        # 天气对应的编码
        self.weather_code = self.read_configs('china_weather.ini', "WeatherCode")
        # 浏览器头
        self.__browser_header = self.read_configs('crawler.ini', "BrowserHeader")

    @staticmethod
    def __check_file_path() -> None:
        """
            检查所需要的文件夹路径, 如果不存在就及时创建
        """
        current_path = os.path.dirname(__file__)
        path_check = [
            os.path.join(current_path, "..", "download"),
            os.path.join(current_path, "..", "download", "rain_charts"),
            os.path.join(current_path, "..", "download", "radar_charts"),
            os.path.join(current_path, "..", "download", "cloud_charts")
        ]
        for path in path_check:
            if not os.path.exists(path):
                os.makedirs(path)

    @staticmethod
    def read_configs(file_name, section) -> dict:
        """
            根据 配置文件名称 和 配置文件分段名称 读取配置文件，转化成dict
        :param file_name: 配置文件名称
        :param section: 配置文件分段的名称
        :return: 配置文件对应分段的数据字典
        """
        current_path = os.path.dirname(__file__)
        city_code_file = os.path.join(current_path, 'configs', file_name)
        if not os.path.isfile(city_code_file):
            raise Exception("配置文件(./configs/" + file_name + ")不存在")
        config = configparser.ConfigParser()
        config.read(city_code_file)
        section_dict = dict(config[section].items())
        return section_dict

    def get_city_code(self, city_name: str) -> str:
        """
            根据城市中文名,查询字典,返回城市的代码
        :param city_name: 城市名称
        :return: 城市代码
        """
        if city_name in self.city_code_dict.keys():
            return self.city_code_dict[city_name]
        raise ValueError('城市名称错误或不在已知编码清单内!')

    def __get_html(self, url: str) -> str:
        """
            请求天气信息页面
        :param url: 请求URL地址
        :return: 请求结果的字符串
        """
        response = requests.request('GET', url, headers=self.__browser_header, timeout=5)
        response.encoding = "utf-8"
        return response.text

    def get_real_time_weather(self, city_name: str) -> dict:
        """
            获取最近更新的天气数据
            暂定每10分钟调用一次
        :param city_name: 城市名称
        :return: 最新天气信息的字典
        """
        city_code = self.get_city_code(city_name)
        url = self.base_urls["实时天气"].format(city_code=city_code)
        try:
            html = self.__get_html(url)
        except:
            return {"错误": url + "请求无响应"}
        data = str(html).replace("var dataSK = ", "")
        data = json.loads(data)
        if 'time' not in data:
            return {"错误": "接口解析错误"}
        result = {
            "更新时间": data['time'],
            "日期": data['date'],
            "城市": data['cityname'],
            "城市编码": data['city'],
            "温度（摄氏）": data['temp'],
            "温度（华氏）": data['tempf'],
            "风向": data['WD'],
            "湿度": data['SD'],
            "天气": data['weather'],
            "风速": data['wse'].replace("&lt;", "<"),
            "24h降水": data['rain24h'],
            "aqi_pm25": data["aqi_pm25"],
        }
        return result

    def get_7d_weather(self, city_name: str) -> dict:
        """
            解析页面，获取近7天的天气预报
        :param city_name: 城市名称
        :return: 最近7天天气的数据字典
        """
        city_code = self.get_city_code(city_name)
        url = self.base_urls["近7天天气"].format(city_code=city_code)
        try:
            html = self.__get_html(url)
        except:
            return {"错误": url + "请求无响应"}
        try:
            soup = BeautifulSoup(html, 'lxml')
            date_ul = soup.find("ul", class_="date-container").findAll("li")
            blue_ul = soup.find("ul", class_="blue-container sky").findAll("li", class_='blue-item')
            temp_7d_H = eval(re.findall(r"var eventDay =(.*?);", html)[0])
            temp_7d_L = eval(re.findall(r"var eventNight =(.*?);", html)[0])
            update_time = str(re.findall(r"var uptime=(.*?);", html)[0]).replace("\"", "").replace("更新", "")
        except:
            return {"错误": "页面解析错误"}
        data_list = []
        for _date, _temp_H, _temp_L, _wind in zip(date_ul, temp_7d_H, temp_7d_L, blue_ul):
            wind_list = _wind.find("div", class_='wind-container').findAll('i')
            wind_direction = [i.attrs['title'] for i in wind_list]
            one_day_info = {
                '日期': _date.find("p", class_='date').get_text(),
                '日期标识': _date.find("p", class_='date-info').get_text(),
                '最高温度': _temp_H,
                '最低温度': _temp_L,
                '天气': _wind.find("p", class_='weather-info').get_text(),
                '风向': wind_direction,
                '风速': _wind.find("p", class_='wind-info').get_text().replace("\n", ""),
            }
            data_list.append(one_day_info)
        result = {
            '城市': city_name,
            '更新时间': update_time,
            '数据': data_list,
        }
        return result

    def get_15d_weather(self, city_name: str) -> dict:
        """
            解析页面，获取近15天的天气预报
        :param city_name: 城市名称
        :return: 最近15天天气的数据字典
        """
        city_code = self.get_city_code(city_name)
        url = self.base_urls["7至15天天气"].format(city_code=city_code)
        try:
            html = self.__get_html(url)
        except:
            return {"错误": url + "请求无响应"}
        try:
            soup = BeautifulSoup(html, 'lxml')
            date_ul = soup.find("ul", class_="date-container").findAll("li")
            blue_ul = soup.find("ul", class_="blue-container").findAll("li", class_='blue-item')
            temp_15d_H = eval(re.findall(r"var fifDay =(.*?);", html)[0])
            temp_15d_L = eval(re.findall(r"var fifNight =(.*?);", html)[0])
            update_time = soup.find('input', id='update_time').attrs['value']
        except:
            return {"错误": "页面解析错误"}
        data_list = []
        for _date, _temp_H, _temp_L, _wind in zip(date_ul, temp_15d_H, temp_15d_L, blue_ul):
            wind_list = _wind.find("div", class_='wind-container').findAll('i')
            wind_direction = [i.attrs['title'] for i in wind_list]
            one_day_info = {
                '日期': _date.find("p", class_='date').get_text(),
                '日期标识': _date.find("p", class_='date-info').get_text(),
                '最高温度': _temp_H,
                '最低温度': _temp_L,
                '天气': _wind.find("p", class_='weather-info').get_text(),
                '风向': wind_direction,
                '风速': _wind.find("p", class_='wind-info').get_text().replace("\n", ""),
            }
            data_list.append(one_day_info)
        data = {
            '城市': city_name,
            '更新时间': update_time,
            '数据': data_list,
        }
        return data

    def get_hours_weather(self, city_name: str) -> dict:
        """
            获取逐小时的天气数据
        :param city_name: 城市名称
        :return: 最近24小时的天气数据字典
        """
        city_code = self.get_city_code(city_name)
        url = self.base_urls["逐小时天气"].format(city_code=city_code)
        try:
            html = self.__get_html(url)
        except:
            return {"错误": url + "请求无响应"}
        hours_data = eval(re.findall(r"var hour3data=(.*?);", html)[0])[0]
        update_time = eval(re.findall(r"var uptime=(.*?);", html)[0]).replace("更新", "")
        for one_houe_data in hours_data:
            one_houe_data['天气'] = self.weather_code[one_houe_data.pop('ja')]
            one_houe_data['风向'] = self.wind_direction_code[one_houe_data.pop("jd")]
            one_houe_data['温度'] = one_houe_data.pop('jb')
            one_houe_data['日期'] = one_houe_data.pop('jf')
            one_houe_data['风速'] = self.wind_speed_code[one_houe_data.pop('jc')]
        data = {
            '城市': city_name,
            "更新时间": update_time,
            '数据': hours_data,
        }
        return data

    def get_radar_chart_by_file_name(self, file_name):
        """
            根据雷达图文件名构造URL请求,下载对应图片
            将图片保存到对应的文件中
        """
        url = self.base_urls['雷达图下载'].format(file_name=file_name)
        response = requests.get(url, headers=self.__browser_header, timeout=5)
        if "PNG" in response.text and "<!DOCTYPE HTML>" not in response.text:
            file = os.path.join(os.path.dirname(__file__), "..", "download", "radar_charts", file_name)
            with open(file, 'wb') as f:
                f.write(response.content)
                f.close()
        else:
            raise Exception("Requesets error")

    def get_rain_chart_by_file_name(self, file_name):
        """
            根据降雨图文件名构造URL请求,下载对应图片
            将图片保存到对应的文件中
        """
        url = self.base_urls['降水图下载'].format(file_name=file_name)
        response = requests.get(url, headers=self.__browser_header, timeout=5)
        if "PNG" in response.text and "<!DOCTYPE HTML>" not in response.text:
            current_path = os.path.dirname(__file__)
            file = os.path.join(current_path, "..", "download", "rain_charts", file_name)
            with open(file, 'wb') as f:
                f.write(response.content)
                f.close()
        else:
            raise Exception("Requesets error")

    @staticmethod
    def check_chart_file(folder, filename) -> bool:
        """
            检查图片文件是否已存在
        :param folder: 文件存储的文件夹
        :param filename: 待检查的文件名
        :return: 存在返回True，不存在返回False
        """
        current_path = os.path.dirname(__file__)
        file = os.path.join(current_path, "..", "download", folder, filename)
        if os.path.exists(file):
            return True
        else:
            return False

    def check_rain_chart(self):
        """
            查询新的 实时降雨量的图片 是否有更新, 将当前没有的图片信息下载到download文件夹
        """
        time_stamp = int(time.time()) * 1000
        url = self.base_urls["降水图列表"].format(time_stamp=str(time_stamp))
        response = requests.get(url, headers=self.__browser_header, timeout=5)
        result = eval(re.findall(r"getPreObs1h\({\"datas\": (.*?)}\)", response.text)[0])
        for item in result:
            if not self.check_chart_file("rain_charts", item["picPath"]):
                self.get_rain_chart_by_file_name(item["picPath"])

    def check_radar_chart(self):
        """
            查询新的 雷达图 是否有更新, 将当前没有的图片信息下载到download文件夹
        """
        time_stamp = int(time.time()) * 1000
        url = self.base_urls["雷达图列表"].format(time_stamp=str(time_stamp))
        response = requests.get(url, headers=self.__browser_header, timeout=5)
        result = eval(re.findall(r"readRadarList\({\"datas\": (.*?)}\)", response.text)[0])
        for item in result:
            if not self.check_chart_file("radar_charts", item["fn"]):
                self.get_radar_chart_by_file_name(item["fn"])

    def get_cloud_chart_by_file_name(self, file_name):
        """
            根据云图文件名构造URL请求,下载对应图片
            将图片保存到对应的文件中
        """
        header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/67.0.3396.79 Safari/537.36',
            'Referer': 'http://www.weather.com.cn/satellite/'
        }
        url = self.base_urls['云图下载'].format(file_name=str(file_name))
        print(url)
        response = requests.get(url, headers=header, timeout=5)
        if "JFIF" in response.text and "<!DOCTYPE HTML>" not in response.text:
            current_path = os.path.dirname(__file__)
            file = os.path.join(current_path, "..", "download", "cloud_charts", file_name)
            with open(file, 'wb') as f:
                f.write(response.content)
                f.close()
        else:
            raise Exception("Requesets error")

    def check_cloud_chart(self):
        """
            查询新的 雷达图 是否有更新, 将当前没有的图片信息下载到download文件夹
        """
        time_stamp = int(time.time()) * 1000
        url = self.base_urls["云图列表"].format(time_stamp=str(time_stamp))
        response = requests.get(url, headers=self.__browser_header, timeout=5)
        result = eval(re.findall(r"readSatellite\((.*?)\)", response.text)[0])
        for item in result["radars"]:
            file_name = "sevp_nsmc_" + item["fn"] + "_lno_py_" + item["ft"] + ".jpg"
            if not self.check_chart_file("cloud_charts", file_name):
                self.get_cloud_chart_by_file_name(file_name)


if __name__ == "__main__":
    # 功能测试
    a = WeatherCrawler()
    print(json.dumps(a.get_real_time_weather("泰安"), ensure_ascii=False, sort_keys=True, indent=4,
                     separators=(', ', ': ')))
    print(json.dumps(a.get_7d_weather("泰安"), ensure_ascii=False, sort_keys=True, indent=4, separators=(', ', ': ')))
    print(json.dumps(a.get_15d_weather("泰安"), ensure_ascii=False, sort_keys=True, indent=4, separators=(', ', ': ')))
    print(json.dumps(a.get_hours_weather("泰安"), ensure_ascii=False, sort_keys=True, indent=4, separators=(', ', ': ')))
    # a.check_cloud_chart()
    # a.check_radar_chart()