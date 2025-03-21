from datetime import datetime, date, timezone, timedelta
import json
import random

from .config import global_config
from .logger import register_logger
from .llmapi import llmApi

logger = register_logger('schedule_generator',global_config.log_level)

class routine:
    def __init__(self, start_time: int,task: str):
        self.start_time: int = start_time
        self.task: str = task


class scheduleGenerator:
    def __init__(self):
        self.yesterday_schedule:list[routine] = []
        self.today_schedule:list[routine] = []
        self.today_schedule_text:str = ""
        self.time_zone = timezone(timedelta(hours=global_config.time_zone))
        self.date = datetime.now(self.time_zone).day
        self.llm_api = llmApi(global_config.gpt_settings)
        self._init_today_schedule()

    def _init_today_schedule(self):
        weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][date.today().weekday()]
        resp = self.llm_api.send_request_text(
            f"""<information>{global_config.bot_config['personality']}</information><task>你昨天的日程安排是f{self.today_schedule_text}。今天是{weekday}，"""+"""你可以参考昨天的日程生成今天的日程安排，但尽量有变化。请按照时间顺序列出具体时间点和对应的活动，格式为{"开始时间": "活动","开始时间": "活动",...}，注意只需要给出开始时间而不是一个时间段。请用活动概括整个时间段需要进行的事件，活动名称不要出现准备/开始等词语，最后一项活动固定为睡觉。用JSON格式返回日程表，仅返回内容，不要返回注释，不要添加任何markdown或代码块样式，时间采用24小时制。</task>"""
        )
        try:
            raw = json.loads(resp)
            schedule = []
            for k,v in raw.items():
                stamp = k.split(":")
                stamp = int(stamp[0])*60 + int(stamp[1])
                schedule.append(routine(stamp,v))
            self.yesterday_schedule = self.today_schedule if self.today_schedule else schedule
            self.today_schedule = schedule
            self.today_schedule_text = resp
            logger.info(f"初始化今日日程->{resp}")
            return True
        except Exception as e:
            logger.error(f"初始化今日日程失败->{e}")
            return False

    def get_current_task(self):
        cur_date = datetime.now(self.time_zone).day
        if self.date != cur_date:
            if self._init_today_schedule():
                self.date = cur_date
        stamp = datetime.now(self.time_zone).hour * 60 + datetime.now(self.time_zone).minute
        logger.debug(f"当前时间戳->{stamp}")
        if self.today_schedule == []:
            return "摸鱼"
        if stamp < self.today_schedule[0].start_time:
            return self.yesterday_schedule[-1].task
        for i in range(len(self.today_schedule)-1):
            if self.today_schedule[i].start_time <= stamp < self.today_schedule[i+1].start_time:
                return self.today_schedule[i].task if random.random() < 0.8 else "摸鱼"
        return self.today_schedule[-1].task if random.random() < 0.8 else "摸鱼"

if __name__ == "__main__":
    from config import global_config
    schedule_generator = scheduleGenerator()
    print(schedule_generator.get_current_task())