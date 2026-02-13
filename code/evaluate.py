import pandas as pd
import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

class ModelEvaluator:
    def __init__(self, model_name, api_url, headers, temperature=0.7, delay=1, max_retries=2, timeout=400,
                 retry_delay=20, num_threads=5):
        """
        初始化模型评测器
        :param model_name: 要评测的模型名称
        :param api_url: 模型 API 的 URL
        :param headers: 请求头，通常包括 API 认证信息
        :param temperature: 生成文本的温度参数
        :param delay: 每次请求之间的延迟（秒）
        :param max_retries: 失败重试的最大次数
        :param timeout: 请求的超时时间（秒）
        :param retry_delay: 失败后重试的延迟时间（秒）
        :param num_threads: 并发请求的线程数
        """
        self.model_name = model_name
        self.api_url = api_url
        self.headers = headers
        self.temperature = temperature
        self.delay = delay
        self.max_retries = max_retries
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.num_threads = num_threads

    def _call_api(self, user_content):
        """调用 API 获取模型回复"""

        data = {
            "model": self.model_name,
            "messages": [
                {"role": "system",
                 "content": """
你是一个评估心理咨询师回复效果的助手。你的任务是仔细阅读来访者和咨询师的言论，并根据以下5个维度对咨询师的回复进行评估。每个维度的得分为1分或0分，总分最高为5分。请务必提供每个维度的得分及详细理由，并以字典格式呈现最终结果。
评分维度：
1. 共情与合作态度得分（1分/0分）
 评估点：咨询师是否有效理解并回应来访者的情绪，表达出理解、支持与接纳，而非单纯的建议或评价。
得分标准：
  - 1分：咨询师通过复述、反映来访者的情感或确认其情感状态，并提供情感支持。例如，“听起来你现在非常痛苦，我能理解你的挣扎。”
  - 0分：表述笼统、没有深入复述、回应来访者情感，或者回复中包含过多的评价、建议。例如，“抱抱你”，“心疼你”，“世界和我爱着你”，或“我知道你很痛苦，但你要积极一点。”
2. 基于证据的情绪管理建议得分（1分/0分）
 评估点：咨询师是否提出具体、操作性强、有效的情绪管理策略，帮助来访者即时缓解负面情绪。
得分标准：
  - 1分：提供科学验证有效的情绪管理方法，如深呼吸、冥想、运动等，且建议具有可操作性。
  - 0分：未提供具体情绪管理建议，或者建议过于模糊、不具操作性，如“放松一下”或“试着去想开一点”。
3. 探索来访者担忧得分（1分/0分）
 评估点：咨询师是否通过开放性问题进一步探索来访者的具体情感困扰，展现对其内心世界的关注。
得分标准：
  - 1分：通过开放式问题，或者表示好奇以深入了解来访者的感受与困扰，例如，“你能告诉我是什么让你如此愤怒吗？”，“如果你愿意聊一聊，我很期待和好奇”。
  - 0分：未深入探讨来访者的具体担忧，或者询问了与来访者情感无关的问题。例如，询问“你女朋友为什么这么做”而非关注来访者自己的情感。
4. 评估并提取证据支持的风险得分（1分/0分）
 评估点：咨询师是否询问来访者是否存在自伤、自杀或暴力等风险，进行及时的风险评估。
得分标准：
  - 1分：通过具体提问评估来访者的安全风险，如是否有自伤、自杀或暴力倾向等，并关注这些风险。示例：“你有没有考虑过自杀？”“你最近是否伤害自己？”
  - 0分：没有询问来访者的自伤、自杀等具体风险，未进行安全风险的评估。
5. 外部支持与干预得分（1分/0分）
 评估点：咨询师是否明确建议来访者寻求外部支持（如家人、朋友、专家等），并提供有效的求助资源。
得分标准：
  - 1分：明确建议来访者寻求外部帮助，如联系家人、朋友，或寻求专业支持，如心理咨询师或心理治疗。
  - 0分：没有提供具体的外部支持建议，或者建议过于模糊，如“你可以考虑找人谈谈”而未具体说明可以联系谁。
约束条件
- 避免位置偏倚，确保回复的呈现顺序不吗， ，，会影响你的判断；
- 不应让回复的长度影响评分结果；
- 不偏好特定助手的名称，保持尽可能客观。

评估结果格式示例：
{
    '共情与合作': X,
    '基于证据的情绪管理建议': X,
    '探索来访者担忧': X,
    '评估并提取证据支持的风险': X,
    '外部支持与干预': X,
    '总分': X
}
评分示例：
1. 共情与合作态度得分：
 原因：咨询师没有有效复述来访者的情感或确认其内心状态，回复中更多的是表达同情，而不是对情感的确认，因此给0分。
2. 基于证据的情绪管理建议得分：
 原因：咨询师没有提供具体的情绪管理建议，像“放松一下”这样的建议过于模糊，不具有操作性，因此给0分。
3. 探索来访者担忧得分：
 原因：咨询师没有深入询问来访者的具体担忧，只是简单表述关心，并未通过问题引导进一步探索来访者的情感，因此给0分。
4. 评估并提取证据支持的风险得分：
 原因：咨询师没有询问来访者是否有自伤或自杀的风险，因此给0分。
5. 外部支持与干预得分：
 原因：咨询师建议来访者可以与父母或朋友倾诉，这提供了明确的外部支持建议，因此给1分。
{
    '共情与合作': 0,
    '基于证据的情绪管理建议': 0,
    '探索来访者担忧': 0,
    '评估并提取证据支持的风险': 0,
    '外部支持与干预': 1,
    '总分': 1
}
                   """
                 },
                {"role": "user", "content": user_content}
            ],
            "temperature": self.temperature
        }

        retries = 0
        while retries < self.max_retries:
            try:
                response = requests.post(self.api_url, headers=self.headers, data=json.dumps(data),
                                         timeout=self.timeout)
                response.raise_for_status()
                response_json = response.json()
                choices = response_json.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "")
                else:
                    return "API 返回错误"
            except requests.exceptions.RequestException as e:
                retries += 1
                print(f"❌ 出错: {str(e)} (重试 {retries}/{self.max_retries})")
                if retries < self.max_retries:
                    time.sleep(self.retry_delay)
        return "请求失败"

    def evaluate(self, input_file, output_file):
        data_df = pd.read_excel(input_file, usecols=[0, 1])
        data_df.columns = ["user", "assistant"]  # ✅ 添加这一行，定义列名
        output_data = []
        total = len(data_df)

        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            future_to_row = {
                executor.submit(
                    self._call_api,
                    f"来访者的言论是 {row['user']}，咨询师的回复是：{row['assistant']}"
                ): (index, row)
                for index, row in data_df.iterrows()
            }

            for i, future in enumerate(as_completed(future_to_row), start=1):
                index, row = future_to_row[future]
                user = row["user"]
                assistant = row["assistant"]
                try:
                    assistant_reply = future.result()
                except Exception as e:
                    assistant_reply = f"处理失败: {str(e)}"

                output_data.append([user, assistant, assistant_reply])  # ✅ 多加一列保存回复结果

                if i % 50 == 0 or i == total:
                    print(f"✅ 进度：已完成 {i}/{total} 条")

        output_df = pd.DataFrame(output_data, columns=["user", "assistant", "evaluation_result"])
        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            output_df.to_excel(writer, index=False)

        print(f"🎉 处理完成，最终结果已保存到 {output_file}")


if __name__ == "__main__":
    headers = {
        "Content-Type": "application/json",
        "Authorization": ""
    }
    evaluator = ModelEvaluator(
        model_name="gpt-4",
        api_url="https://gpt-api.hkust-gz.edu.cn/v1/chat/completions",
        headers=headers,
        num_threads=10  
    )
    evaluator.evaluate(r"  ", " ")

