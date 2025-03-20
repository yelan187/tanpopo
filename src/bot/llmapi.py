import base64
from openai import OpenAI

class llmApi:
    """
    处理与llm交互
    """
    def __init__(self,settings:dict):
        self.client = OpenAI(api_key=settings["api_key"],base_url=settings["base_url"])
        self.chat_model = settings["chat_model"]
        self.image_model = settings["image_model"]
        self.stream = settings["stream"]

    def send_request_text(self,prompt:str) -> str:
        """
        发送文本请求
        """
        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "user", "content": prompt},
            ],
            stream=self.stream
        )
        if self.stream:
            resp = ""
            for chunk in response:
                resp += chunk.choices[0].delta.content
            return resp
        else:
            return response.choices[0].message.content
        
    def send_request_image(self,prompt:str,image_base64:str) -> str:
        """
        发送图片请求
        图片格式为base64编码的jpeg
        """
        response = self.client.chat.completions.create(
            model=self.image_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                },
            ]
        )
        return response.choices[0].message.content

if __name__ == "__main__":
    def encode_image(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    from config import global_config
    llmapi = llmApi(global_config.gpt_settings)
    img_base64 = encode_image("/Users/xuyitian/Downloads/avatar.jpeg")
    print(llmapi.send_request_image("请用几个词描述这张图片",img_base64))
