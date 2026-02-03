import os
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class NetworkArchitectAI:
    def __init__(self):
        api_key = os.getenv("AI_API_KEY")
        base_url = os.getenv("AI_BASE_URL")

        # 二次验证（防御性编程）
        if not api_key or not base_url:
            raise ValueError("环境变量 AI_API_KEY 或 AI_BASE_URL 未设置")
        if not base_url.rstrip("/").endswith("/v1"):
            raise ValueError(f"AI_BASE_URL 必须以 /v1 结尾，当前值: {base_url}")

        try:
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url  # 确保是 https://api.deepseek.com/v1
            )
        except Exception as e:
            # 提供可操作的错误信息（参考知识库 [3][7]）
            if "401" in str(e) or "authentication" in str(e).lower():
                raise RuntimeError("API 密钥无效或已过期，请检查 Secrets 中的 AI_API_KEY") from e
            elif "base_url" in str(e).lower() or "invalid url" in str(e).lower():
                raise RuntimeError(f"base_url 格式错误: {base_url}。必须为 https://api.deepseek.com/v1") from e
            else:
                raise RuntimeError(f"OpenAI 客户端初始化失败: {str(e)}") from e

    def get_diagnostic_response(self, user_code, user_thought, topic):
        """
        S1 升级版：加入学生自己的思考（user_thought）
        """
        system_prompt = f"""
        你是一位苏格拉底式的网络工程导师。
        当前实验主题：{topic}

        【输入信息】：
        1. 学生代码/日志：(见用户输入)
        2. 学生对自己错误的预判：{user_thought}

        【你的回复逻辑】：
        1. 首先点评学生的"预判"是否准确。如果学生猜对了方向，给予肯定；如果猜错了，指出为什么那个方向不是问题的根源。
        2. 然后再分析代码中的实际错误。
        3. 不要直接给代码！通过提问引导。例如："你注意到了 Area ID，但你检查过掩码的反码格式吗？"
        4. 使用 Markdown 格式，语气亲切但专业。
        """

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_code}
                ],
                stream=True,
                temperature=0.4
            )
            return response
        except Exception as e:
            return f"AI 连接中断: {str(e)}"

    def generate_personalized_task(self, learning_topic, mastery_level):
        """
        S3 升级版：基于今日学习内容的动态生成
        """
        task_prompt = f"""
        我是《计算机与网络》课程的学生。
        【今日学习重点】：{learning_topic}
        【我的自评掌握度】：{mastery_level}

        请为我设计一个通过 Packet Tracer 或 GNS3 完成的实战任务。

        要求：
        1. 如果掌握度是"刚入门"，任务要包含详细的步骤提示。
        2. 如果是"已熟练"，任务要包含 2-3 个隐蔽的故障陷阱（Troubleshooting）。
        3. 必须紧扣"{learning_topic}"这个主题。

        输出结构：
        ### 🎯 今日挑战目标
        ### 🧩 拓扑构建要求
        ### 💣 预埋故障/配置任务
        ### 🔍 验收标准 (Ping/Show命令)
        """

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": task_prompt}],
                stream=True
            )
            return response
        except Exception as e:
            return f"任务生成失败: {str(e)}"

    def generate_task_solution(self, task_content):
        """
        S3 新增功能：根据已生成的任务，生成对应的参考答案
        """
        solution_prompt = f"""
        你是一位专业的网络工程师。请根据以下生成的实验任务，提供标准的参考答案。

        【任务内容回顾】：
        {task_content}

        【输出要求】：
        1. 分设备列出配置命令（Cisco IOS格式优先）。
        2. 解释关键配置的作用。
        3. 给出 1-2 个核心验证命令（show xxx）及其预期输出。
        4. 格式清晰，代码放入 Markdown 代码块中。
        """
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": solution_prompt}],
                stream=True
            )
            return response
        except Exception as e:
            return f"答案生成失败: {str(e)}"


    def socratic_quiz(self, concept):
        """
        新增功能：概念追问
        """
        prompt = f"""
        用最通俗易懂的比喻解释"{concept}"这个网络概念，
        然后向我抛出一个有深度的思考题，测试我是否真的理解了。
        """
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                stream=True
            )
            return response
        except Exception as e:
            return f"Error: {str(e)}"