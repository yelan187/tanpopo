FROM python:3.10

WORKDIR /tanpopo

# 安装项目依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 项目初始环境配置
COPY . .
RUN mkdir tmp

CMD cp ./onebot11.json /napcat/onebot11.json && python script/init_memory_db.py && python run.py