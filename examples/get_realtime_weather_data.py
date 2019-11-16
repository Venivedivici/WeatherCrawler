from WeatherCrawler import WeatherCrawler
import json

crawler = WeatherCrawler()
result = crawler.get_real_time_weather("北京")
print(json.dumps(result,
                 ensure_ascii=False,
                 sort_keys=True,
                 indent=4))
