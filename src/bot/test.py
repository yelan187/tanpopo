from datetime import datetime, timezone, timedelta

# 创建自定义时区（例如：UTC+5）
my_timezone = timezone(timedelta(hours=8))

# 获取当前时间，并应用时区
current_time = datetime.now(my_timezone)

# 提取日期部分
day = current_time.day  # 只获取日期
print(f"Day: {day}")

# 提取时间部分
time = current_time.time()  # 获取时间
print(f"Time: {time}")
