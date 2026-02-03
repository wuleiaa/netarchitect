# ====== 必须放在最最顶部！清除代理冲突 ======
import os

# 删除所有可能触发代理的环境变量（关键！）
for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'OPENAI_PROXY']:
    if proxy_var in os.environ:
        del os.environ[proxy_var]
# ===============================================

# 统一导入（避免重复）
from utils.db_helper import get_db_path  # 仅此一处导入
import streamlit as st
from utils.ai_engine import NetworkArchitectAI
from datetime import datetime  # 导入 datetime 类
import sqlite3
import hashlib

# ========== 全局状态初始化（关键：显式初始化所有状态） ==========
# 基础状态
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = None
if "show_register" not in st.session_state:
    st.session_state.show_register = False  # 注册弹窗状态
if "debug_save" not in st.session_state:
    st.session_state.debug_save = []  # 初始化调试日志列表

# AI引擎状态
if "ai_engine" not in st.session_state:
    st.session_state.ai_engine = None

# 学习进度状态
if "weekly_progress_count" not in st.session_state:
    st.session_state.weekly_progress_count = 0  # 初始为 0

# S1 智能诊断状态
if "s1_diagnosis_history" not in st.session_state:
    st.session_state.s1_diagnosis_history = ""
if "s1_chat_history_list" not in st.session_state:
    st.session_state.s1_chat_history_list = []
if "s1_active_history_index" not in st.session_state:
    st.session_state.s1_active_history_index = None

# S3 自适应实验状态
if "s3_task_text" not in st.session_state:
    st.session_state.s3_task_text = ""
if "s3_solution_text" not in st.session_state:
    st.session_state.s3_solution_text = ""
if "s3_show_answer" not in st.session_state:
    st.session_state.s3_show_answer = False  # 显式初始化
if "current_task_scored" not in st.session_state:
    st.session_state.current_task_scored = False  # 显式初始化
if "s3_chat_history_list" not in st.session_state:
    st.session_state.s3_chat_history_list = []
if "s3_active_history_index" not in st.session_state:
    st.session_state.s3_active_history_index = None

# 原理追问状态
if "deep_inquiry_history" not in st.session_state:
    st.session_state.deep_inquiry_history = ""
if "inquiry_chat_history_list" not in st.session_state:
    st.session_state.inquiry_chat_history_list = []
if "inquiry_active_history_index" not in st.session_state:
    st.session_state.inquiry_active_history_index = None

# 删除模式状态
if "delete_mode" not in st.session_state:
    st.session_state.delete_mode = False
if "delete_menu" not in st.session_state:
    st.session_state.delete_menu = None


# ====== 数据库初始化 ======
def init_db():
    # 云端持久化路径（统一用get_db_path）
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    c = conn.cursor()

    # 用户表
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # 对话历史表（统一存储三个模块）
    c.execute('''CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        module TEXT NOT NULL,  -- 's1', 's3', 'inquiry'
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        solution TEXT,         -- 仅s3需要
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    conn.commit()
    conn.close()


# 初始化数据库（应用启动时调用）
init_db()


# ====== 新增：用户认证函数 ======
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(username, password):
    try:
        conn = sqlite3.connect(get_db_path(), check_same_thread=False)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                  (username, hash_password(password)))
        conn.commit()
        conn.close()
        return True, "注册成功！请登录"
    except sqlite3.IntegrityError:
        return False, "用户名已存在"


def authenticate_user(username, password):
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username = ? AND password_hash = ?",
              (username, hash_password(password)))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def load_user_conversations(user_id):
    """加载用户所有历史对话"""
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    c = conn.cursor()

    # 加载S1历史
    c.execute(
        "SELECT title, content FROM conversations WHERE user_id = ? AND module = 's1' ORDER BY created_at DESC LIMIT 10",
        (user_id,))
    s1_list = [{"title": row[0], "content": row[1]} for row in c.fetchall()]

    # 加载S3历史
    c.execute(
        "SELECT title, content, solution FROM conversations WHERE user_id = ? AND module = 's3' ORDER BY created_at DESC LIMIT 10",
        (user_id,))
    s3_list = [{"title": row[0], "content": row[1], "solution": row[2] or ""} for row in c.fetchall()]

    # 加载追问历史
    c.execute(
        "SELECT title, content FROM conversations WHERE user_id = ? AND module = 'inquiry' ORDER BY created_at DESC LIMIT 10",
        (user_id,))
    inquiry_list = [{"title": row[0], "content": row[1]} for row in c.fetchall()]

    conn.close()
    return s1_list, s3_list, inquiry_list


def save_conversation(user_id, module, title, content, solution=None):
    """保存单条对话到数据库"""
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    c = conn.cursor()
    c.execute("INSERT INTO conversations (user_id, module, title, content, solution) VALUES (?, ?, ?, ?, ?)",
              (user_id, module, title, content, solution))
    conn.commit()
    conn.close()


# 1. 页面配置
st.set_page_config(
    page_title="NetArchitect - 智能网络实验台",
    page_icon="🖥️",
    layout="wide"
)

# ========== CSS 样式注入 (浅绿色背景 + 细节优化) ==========
st.html("""
<style>
/* ===== 手机文字强制可见（深色/浅色模式通吃）===== */
* {
    color: #2D3748 !important; /* 深灰文字 */
}
/* 1. 全局背景色 - 云雾灰 (高端、护眼、突出卡片感) */
.stApp {
    background-color: #F5F7F8;
    color: #333333;
}
/* 顶部 Header 背景色 */
header[data-testid="stHeader"] {
    background-color: #F5F7F8;
}

/* 2. 侧边栏 - 强制纯白 */
section[data-testid="stSidebar"] {
    background-color: #FFFFFF !important;
    border-right: 1px solid #E0E0E0;
}
section[data-testid="stSidebar"] > div {
    background-color: #FFFFFF !important;
}

/* ========== 3. 按钮样式优化（关键修改！） ========== */
/* 浅绿背景 + 纯黑字体（WCAG AA级对比度 12.5:1） */
div.stButton > button,
div.stDownloadButton > button,
button[kind="secondary"],
button[kind="primary"] {
    background-color: #A5D6A7 !important;  /* 柔和浅绿（非刺眼） */
    color: #000000 !important;             /* 纯黑字体（清晰锐利） */
    border-radius: 8px !important;
    border: none !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.2rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 4px rgba(165, 214, 167, 0.3) !important;
    background-image: none !important;
}

/* 悬停效果：稍深绿 + 黑字保持 */
div.stButton > button:hover,
button[kind="secondary"]:hover,
button[kind="primary"]:hover {
    background-color: #81C784 !important;  /* 悬停加深 */
    color: #000000 !important;
    box-shadow: 0 4px 8px rgba(129, 199, 132, 0.4) !important;
    transform: translateY(-1px) !important;
}

/* 按下效果 */
div.stButton > button:active {
    transform: translateY(0) !important;
    box-shadow: 0 2px 4px rgba(165, 214, 167, 0.3) !important;
}

/* 禁用状态：极浅绿 + 深灰字（仍清晰可辨） */
div.stButton > button:disabled,
button[kind="secondary"]:disabled,
button[kind="primary"]:disabled {
    background-color: #E8F5E9 !important;
    color: #666666 !important;
    cursor: not-allowed !important;
    opacity: 1 !important;
}

/* 4. 输入框/文本框 */
.stTextArea textarea, 
.stTextInput input, 
.stSelectbox div[data-baseweb="select"] {
    background-color: #FFFFFF;
    border: 1px solid #D1D5DB;
    border-radius: 6px;
}
.stTextArea textarea {
    border: 1px solid #a5d6a7;
}

/* 6. 进度条颜色同步优化（浅绿系） */
.stProgress > div > div > div > div {
    background-color: #A5D6A7 !important;
}

/* 7. 导师反馈气泡框 */
[data-testid="stChatMessage"] {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 15px;
    margin-top: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
/* 机器人头像背景色 */
[data-testid="stChatMessageAvatarBackground"] {
    background-color: #1976D2;
}
</style>
""")

# ========== 配置校验（关键：改用st.secrets，命名统一） ==========
# 从Streamlit Secrets读取配置（适配Cloud环境）
ai_api_key = st.secrets.get("OPENAI_API_KEY")  # 统一为OPENAI_API_KEY
ai_base_url = st.secrets.get("AI_BASE_URL")

# 严格验证
if not ai_api_key:
    st.error("❌ **OPENAI_API_KEY 未配置**\n请在 Streamlit Cloud → Manage app → Secrets 中添加：\n`OPENAI_API_KEY = sk-你的密钥`")
    st.stop()
if not ai_base_url:
    st.error("❌ **AI_BASE_URL 未配置**\n请在 Secrets 中添加：\n`AI_BASE_URL = https://api.deepseek.com/v1`")
    st.stop()
if not ai_base_url.rstrip("/").endswith("/v1"):
    st.error(f"❌ **AI_BASE_URL 格式错误**\n当前值: `{ai_base_url}`\n✅ 正确格式: `https://api.deepseek.com/v1`\n（必须包含 `/v1` 后缀）")
    st.stop()

# ========== 安全初始化AI引擎（带异常处理） ==========
if st.session_state.ai_engine is None:
    try:
        st.session_state.ai_engine = NetworkArchitectAI()
    except Exception as e:
        st.error(f"❌ AI 引擎初始化失败: {str(e)}")
        st.info("请检查 Secrets 中的密钥和 URL 是否正确")
        st.stop()

# =============== 居中登录界面 ===============
if st.session_state.user_id is None:
    # 居中容器
    st.markdown("""
        <div style="display: flex; justify-content: center; align-items: center; min-height: 70vh;">
            <div style="width: 420px; padding: 35px; background: white; border-radius: 16px; 
                       box-shadow: 0 10px 30px rgba(0,0,0,0.12); text-align: center;">
                <h2 style="color: #2E7D32; margin-bottom: 10px;">🖥️ NetArchitect</h2>
                <p style="color: #555; margin-bottom: 25px;">智能网络实验教学平台</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 登录表单（居中列）
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            st.text_input("👤 用户名", key="login_username")
            st.text_input("🔑 密码", type="password", key="login_password")
            submit = st.form_submit_button("🔐 登录", use_container_width=True, type="primary")

            if submit:
                uid = authenticate_user(st.session_state.login_username, st.session_state.login_password)
                if uid:
                    st.session_state.user_id = uid
                    st.session_state.username = st.session_state.login_username
                    # 加载历史
                    s1_h, s3_h, iq_h = load_user_conversations(uid)
                    st.session_state.s1_chat_history_list = s1_h
                    st.session_state.s3_chat_history_list = s3_h
                    st.session_state.inquiry_chat_history_list = iq_h
                    st.success(f"🎉 欢迎回来，{st.session_state.username}！")
                    st.rerun()
                else:
                    st.error("❌ 用户名或密码错误")

        # 注册区
        st.markdown("---")
        if st.button("✨ 没有账号？立即注册", use_container_width=True):
            st.session_state.show_register = True

        if st.session_state.show_register:
            with st.form("reg_form"):
                ru = st.text_input("新用户名", key="reg_user")
                rp = st.text_input("新密码", type="password", key="reg_pass")
                rsub = st.form_submit_button("✅ 注册", use_container_width=True)
                if rsub:
                    ok, msg = register_user(ru, rp)
                    if ok:
                        st.success(msg)
                        st.session_state.show_register = False
                        st.session_state.login_username = ru  # 自动填充
                    else:
                        st.error(msg)

    st.stop()  # ⚠️ 关键：阻止后续功能模块渲染
# =============== 登录界面结束 ===============

# ==================== 侧边栏配置 ====================
with st.sidebar:
    # 已登录状态：显示用户信息和登出按钮
    st.title(f"👨‍💻 欢迎 {st.session_state.username}")
    if st.button("🚪 退出登录", use_container_width=True):
        # 清除所有用户相关状态
        for key in ["user_id", "username", "s1_chat_history_list",
                    "s3_chat_history_list", "inquiry_chat_history_list"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    # 图片加载（修复笔误）
    try:
        st.image("xinkecolorlog.png", use_container_width=True)
    except:
        st.error("⚠️ 请将 xinkecolorlog.png 复制到项目根目录")
    st.write("")  # 加一行空行，增加一点呼吸感
    st.image("server.png", width=60)

    st.title("👨‍💻 学生控制台")
    st.caption("Ver 2.0 | 智能教学版")
    st.markdown("---")

    # 导航栏
    menu = st.radio(
        "功能导航",
        ["🔍 网络智能诊断", "🎯 自适应实验工场", "🧠 协议认知诊断"],
        index=0
    )

    st.markdown("---")

    # 删除模式按钮
    if st.button("🗑️ 删除模式", use_container_width=True):
        st.session_state.delete_mode = not st.session_state.delete_mode
        st.session_state.delete_menu = menu
        st.rerun()

    # 根据菜单项显示不同的历史记录
    if menu == "🔍 网络智能诊断":
        st.markdown("#### 🕒 历史对话")

        # 1. 新建对话按钮
        if st.button("➕ 新建对话", use_container_width=True):
            st.session_state.s1_active_history_index = None
            st.session_state.s1_diagnosis_history = ""
            st.rerun()

        # 2. 循环显示历史记录 (倒序)
        for i, chat in enumerate(reversed(st.session_state.s1_chat_history_list)):
            real_index = len(st.session_state.s1_chat_history_list) - 1 - i
            display_title = (chat['title'][:10] + '..') if len(chat['title']) > 10 else chat['title']

            # 删除模式
            if st.session_state.delete_mode and st.session_state.delete_menu == "🔍 网络智能诊断":
                if st.button(f"❌ {display_title}", key=f"del_s1_{real_index}"):
                    deleted_record = st.session_state.s1_chat_history_list.pop(real_index)
                    # 统一用get_db_path()删除
                    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
                    c = conn.cursor()
                    c.execute("""DELETE FROM conversations 
                                    WHERE user_id = ? AND module = 's1' AND title = ?""",
                              (st.session_state.user_id, deleted_record['title']))
                    conn.commit()
                    conn.close()
                    if st.session_state.s1_active_history_index == real_index:
                        st.session_state.s1_active_history_index = None
                    st.rerun()
            else:
                if st.button(f"📄 {display_title}", key=f"hist_{real_index}"):
                    st.session_state.s1_active_history_index = real_index
                    st.rerun()

    elif menu == "🎯 自适应实验工场":
        st.markdown("#### 🕒 历史对话")

        # 1. 新建对话按钮
        if st.button("➕ 新建对话", use_container_width=True):
            st.session_state.s3_active_history_index = None
            if "s3_task_text" in st.session_state:
                del st.session_state.s3_task_text
            st.session_state.s3_solution_text = ""
            st.session_state.s3_show_answer = False
            st.rerun()

        # 2. 循环显示历史记录 (倒序)
        for i, chat in enumerate(reversed(st.session_state.s3_chat_history_list)):
            real_index = len(st.session_state.s3_chat_history_list) - 1 - i
            display_title = (chat['title'][:10] + '..') if len(chat['title']) > 10 else chat['title']

            # 删除模式
            if st.session_state.delete_mode and st.session_state.delete_menu == "🎯 自适应实验工场":
                if st.button(f"❌ {display_title}", key=f"del_s3_{real_index}"):
                    deleted_record = st.session_state.s3_chat_history_list.pop(real_index)
                    # 统一用get_db_path()删除
                    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
                    c = conn.cursor()
                    c.execute("""DELETE FROM conversations 
                                    WHERE user_id = ? AND module = 's3' AND title = ?""",
                              (st.session_state.user_id, deleted_record['title']))
                    conn.commit()
                    conn.close()
                    if st.session_state.s3_active_history_index == real_index:
                        st.session_state.s3_active_history_index = None
                    st.rerun()
            else:
                if st.button(f"📄 {display_title}", key=f"s3_hist_{real_index}"):
                    st.session_state.s3_active_history_index = real_index
                    st.rerun()

    elif menu == "🧠 协议认知诊断":
        st.markdown("#### 🕒 历史对话")

        # 1. 新建对话按钮
        if st.button("➕ 新建对话", use_container_width=True):
            st.session_state.inquiry_active_history_index = None
            st.session_state.deep_inquiry_history = ""
            st.rerun()

        # 2. 循环显示历史记录 (倒序)
        for i, chat in enumerate(reversed(st.session_state.inquiry_chat_history_list)):
            real_index = len(st.session_state.inquiry_chat_history_list) - 1 - i
            display_title = (chat['title'][:10] + '..') if len(chat['title']) > 10 else chat['title']

            # 删除模式（修复数据库连接）
            if st.session_state.delete_mode and st.session_state.delete_menu == "🧠 协议认知诊断":
                if st.button(f"❌ {display_title}", key=f"del_inquiry_{real_index}"):
                    deleted_record = st.session_state.inquiry_chat_history_list.pop(real_index)
                    # 统一用get_db_path()删除（核心修复）
                    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
                    c = conn.cursor()
                    c.execute("""DELETE FROM conversations 
                                    WHERE user_id = ? AND module = 'inquiry' AND title = ?""",
                              (st.session_state.user_id, deleted_record['title']))
                    conn.commit()
                    conn.close()
                    if st.session_state.inquiry_active_history_index == real_index:
                        st.session_state.inquiry_active_history_index = None
                    st.rerun()
            else:
                if st.button(f"📄 {display_title}", key=f"inquiry_hist_{real_index}"):
                    st.session_state.inquiry_active_history_index = real_index
                    st.rerun()

    # 显示删除模式提示
    if st.session_state.delete_mode and st.session_state.delete_menu == menu:
        st.warning("⚠️ 已进入删除模式！点击对话标题即可删除。再次点击删除模式按钮退出。")

    # 学习进度显示
    current_count = st.session_state.weekly_progress_count
    progress_percent = min(current_count / 10, 1.0)
    st.write(f"**当前状态 (已完成 {current_count}/10 任务)**")
    st.progress(progress_percent, text="本周学习进度")

    if current_count >= 10:
        st.success("🎉 太棒了！本周学习目标已达成！")
    else:
        st.markdown(f"""
           <div style="background-color: #FFCDD2; border-radius: 4px; padding: 2px;">
               <div style="background-color: #F44336; width: {progress_percent * 100}%; height: 20px; border-radius: 4px; text-align: center; line-height: 20px; color: white; font-size: 12px;">
                   {int(progress_percent * 100)}%
               </div>
           </div>
           """, unsafe_allow_html=True)
        st.caption(f"加油！再完成 {10 - current_count} 个任务即可达成目标 🚀")

    st.info("💡 提示：多思考，少依赖。先尝试自己分析报错原因。")

# ==================== 模块一：智能故障诊疗室 (S1 升级版) ====================
if menu == "🔍 网络智能诊断":
    st.header("🔍 网络智能诊断系统 | AI根因分析引擎")
    st.markdown("遇到 `Ping` 不通？别急着贴代码，先告诉我**你觉得**哪里出了问题。")

    col1, col2 = st.columns([1, 1], gap="medium")

    with col1:
        st.subheader("1. 提交实验数据")
        topic = st.selectbox(
            "🔬 实验主题",
            [
                "OSPF 邻居建立", "VLAN 间路由", "ACL 策略", "NAT 配置", "BGP 属性选路",
                "RIP 路由环路", "STP 根桥选举", "端口安全配置", "DHCP 服务故障", "DNS 解析失败",
                "静态路由配置", "EIGRP 邻居关系", "HSRP/VRRP 网关冗余", "无线AP关联问题", "IPv6 地址配置",
                "QoS 策略应用", "MPLS LDP 邻居", "IPSec VPN 隧道", "防火墙策略拦截", "网络环路检测"
            ],
            index=0
        )

        user_thought = st.text_area(
            "🤔 我的初步排查思路 (必填)",
            height=100,
            placeholder="例如：我觉得是两边的 Hello 时间不一致，或者是接口忘记配 no shutdown..."
        )

        user_code = st.text_area(
            "📋 粘贴设备配置 / 报错日志",
            height=300,
            placeholder="Router# show run..."
        )

        analyze_btn = st.button("提交给 AI 导师", use_container_width=True)

    with col2:
        st.subheader("2. 导师反馈")
        result_box = st.container()

        # 场景 A：用户点击提交
        if analyze_btn:
            if not user_thought:
                st.warning("⚠️ 请先填写你的排查思路！学习不能只靠 AI。")
            elif not user_code:
                st.warning("⚠️ 请粘贴配置代码。")
            else:
                with result_box:
                    with st.chat_message("assistant", avatar="🤖"):
                        st.markdown("#### 🧠 导师正在分析...")
                        stream = st.session_state.ai_engine.get_diagnostic_response(user_code, user_thought, topic)
                        response_text = st.write_stream(stream)
                        st.session_state.s1_diagnosis_history = response_text

                        # 自动存档
                        timestamp = datetime.now().strftime("%H:%M")
                        title = f"[{timestamp}] {topic}"
                        new_record = {"title": title, "content": response_text}
                        st.session_state.s1_chat_history_list.append(new_record)

                        # 保存到数据库
                        save_conversation(
                            user_id=st.session_state.user_id,
                            module="s1",
                            title=title,
                            content=response_text
                        )

                        # 限制存储数量
                        if len(st.session_state.s1_chat_history_list) > 10:
                            st.session_state.s1_chat_history_list.pop(0)
                        st.session_state.s1_active_history_index = None
        # 场景 B：查看历史记录
        elif st.session_state.s1_active_history_index is not None:
            record = st.session_state.s1_chat_history_list[st.session_state.s1_active_history_index]
            with result_box:
                with st.chat_message("assistant", avatar="🤖"):
                    st.caption(f"📂 正在查看历史存档：{record['title']}")
                    st.markdown(record["content"])
        # 场景 C：显示历史对话
        elif st.session_state.s1_diagnosis_history:
            with result_box:
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown("#### 🧠 导师的历史分析...")
                    st.markdown(st.session_state.s1_diagnosis_history)
        # 场景 D：默认提示
        else:
            with result_box:
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown("""
                    👋 **你好！我是你的排错专家。**

                    请在左侧 **提交实验数据**：
                    1. 选择实验主题
                    2. 描述你的排查思路
                    3. 粘贴报错的代码或日志

                    我会在这里为你提供 **启发式诊断建议**，助你找到问题根源！🛠️
                    """)

# ==================== 模块二：自适应实验工场 (S3 升级版) ====================
elif menu == "🎯 自适应实验工场":
    st.header("🎯 自适应实验工场 | 个性化实训生成")
    st.markdown("根据你今天的学习内容，生成专属的练习任务。")

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        today_focus = st.text_input("📅 今日学习重点", placeholder="例如：OSPF 的 DR/BDR 选举")
    with c2:
        level = st.select_slider("📊 我对该知识点的掌握度", options=["完全不懂", "似懂非懂", "基本掌握", "我想挑战极限"])
    with c3:
        st.write("")
        st.write("")
        gen_btn = st.button("生成任务单", type="primary")

    st.markdown("---")

    # 生成任务
    if gen_btn and today_focus:
        st.session_state.s3_show_answer = False
        st.session_state.current_task_scored = False
        st.session_state.s3_solution_text = ""
        with st.spinner(f"正在构建关于【{today_focus}】的拓扑环境..."):
            stream = st.session_state.ai_engine.generate_personalized_task(today_focus, level)
            st.session_state.s3_task_text = st.write_stream(stream)

            # 自动存档
            timestamp = datetime.now().strftime("%H:%M")
            title = f"[{timestamp}] {today_focus}"
            new_record = {"title": title, "content": st.session_state.s3_task_text, "level": level, "solution": ""}
            st.session_state.s3_chat_history_list.append(new_record)

            # 保存到数据库
            save_conversation(
                user_id=st.session_state.user_id,
                module="s3",
                title=title,
                content=st.session_state.s3_task_text
            )

            # 限制存储数量
            if len(st.session_state.s3_chat_history_list) > 10:
                st.session_state.s3_chat_history_list.pop(0)
            st.session_state.s3_active_history_index = None

    # 查看历史任务
    if st.session_state.s3_active_history_index is not None:
        record = st.session_state.s3_chat_history_list[st.session_state.s3_active_history_index]
        st.markdown(record["content"])
        st.markdown("---")

        if record.get("solution"):
            st.subheader("📝 历史参考答案与解析")
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(record["solution"])
            st.session_state.s3_show_answer = True
            st.session_state.s3_solution_text = record["solution"]
    # 显示当前任务
    elif "s3_task_text" in st.session_state and st.session_state.s3_task_text:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(st.session_state.s3_task_text)
    # 默认提示
    else:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown("""
                👋 **欢迎来到动态靶场！**

                这里是你的 **专属实验生成区**。

                1. 在上方输入 **今日学习重点** (如 OSPF, VLAN, NAT)
                2. 拖动滑块调整 **掌握程度**
                3. 点击 **生成任务单**

                AI 将为你量身定制一套 **独一无二** 的实战拓扑与故障挑战！🎯
                """)

    # 查看答案按钮
    if ("s3_task_text" in st.session_state and st.session_state.s3_task_text) or \
            (st.session_state.s3_active_history_index is not None and
             st.session_state.s3_chat_history_list[st.session_state.s3_active_history_index].get("solution")):
        st.markdown("---")

        if st.button("✅ 我做完了，查看参考答案"):
            st.session_state.s3_show_answer = True

            # 加分逻辑（防止重复加分）
            if not st.session_state.current_task_scored:
                if st.session_state.weekly_progress_count < 10:
                    st.session_state.weekly_progress_count += 1
                st.session_state.current_task_scored = True
                st.rerun()

        # 显示答案
        if st.session_state.s3_show_answer:
            st.subheader("📝 参考答案与解析")
            if st.session_state.s3_solution_text:
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(st.session_state.s3_solution_text)

                # 更新历史记录中的答案
                if st.session_state.s3_active_history_index is not None:
                    st.session_state.s3_chat_history_list[st.session_state.s3_active_history_index][
                        "solution"] = st.session_state.s3_solution_text
            else:
                with st.spinner("AI 正在撰写解题思路..."):
                    with st.chat_message("assistant", avatar="🤖"):
                        ans_stream = st.session_state.ai_engine.generate_task_solution(st.session_state.s3_task_text)
                        st.session_state.s3_solution_text = st.write_stream(ans_stream)

                # 更新历史记录中的答案
                if st.session_state.s3_active_history_index is not None:
                    st.session_state.s3_chat_history_list[st.session_state.s3_active_history_index][
                        "solution"] = st.session_state.s3_solution_text
                elif len(st.session_state.s3_chat_history_list) > 0:
                    st.session_state.s3_chat_history_list[-1]["solution"] = st.session_state.s3_solution_text

# ==================== 模块三：原理深度追问 (新增) ====================
elif menu == "🧠 协议认知诊断":
    st.header("🧠 协议认知诊断引擎 | 深度原理探析")
    st.markdown("不写代码，只聊原理。用苏格拉底的方式检验你的理解深度。")

    concept = st.text_input("输入一个让你困惑的概念", placeholder="例如：为什么 TCP 需要三次握手？")

    # 生成追问
    if st.button("开始追问"):
        if concept:
            with st.chat_message("assistant", avatar="🤖"):
                stream = st.session_state.ai_engine.socratic_quiz(concept)
                response_text = st.write_stream(stream)
                st.session_state.deep_inquiry_history = response_text

            # 自动存档
            timestamp = datetime.now().strftime("%H:%M")
            title = f"[{timestamp}] {concept}"
            new_record = {"title": title, "content": response_text}
            st.session_state.inquiry_chat_history_list.append(new_record)

            # 保存到数据库
            save_conversation(
                user_id=st.session_state.user_id,
                module="inquiry",
                title=title,
                content=response_text
            )

            # 限制存储数量
            if len(st.session_state.inquiry_chat_history_list) > 10:
                st.session_state.inquiry_chat_history_list.pop(0)
            st.session_state.inquiry_active_history_index = None
        else:
            st.error("请输入概念名称")

    # 查看历史追问
    elif st.session_state.inquiry_active_history_index is not None:
        record = st.session_state.inquiry_chat_history_list[st.session_state.inquiry_active_history_index]
        with st.chat_message("assistant", avatar="🤖"):
            st.caption(f"📂 正在查看历史存档：{record['title']}")
            st.markdown(record["content"])
    # 显示历史追问
    elif st.session_state.deep_inquiry_history:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(st.session_state.deep_inquiry_history)
    # 默认提示
    else:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown("""
                👋 **你好！我是你的原理导师。**

                请在上方输入你想要深入理解的网络概念（如 OSPF、ARP、TCP等），
                我会用苏格拉底式教学法带你从原理层面攻克它！🚀
                """)