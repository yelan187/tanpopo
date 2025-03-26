FROM python:3.10

WORKDIR /tanpopo

# 安装项目依赖
COPY requirements.txt .
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 项目初始环境配置
COPY . .
RUN mkdir tmp
RUN chmod +x start.sh

CMD ./start.sh && python script/init_memory_db.py && python run.py