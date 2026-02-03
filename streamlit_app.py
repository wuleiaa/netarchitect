from utils.db_helper import get_db_path  # 仅此一处导入
import streamlit as st
from utils.ai_engine import NetworkArchitectAI
from datetime import datetime  # 导入 datetime 类

# ====== 新增：数据库初始化 ======
import sqlite3
import hashlib
import os
# 在文件最顶部添加防护（防止命名冲突）


# 创建数据库连接函数
def init_db():
    # 修改后（云端持久化！）
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
        # 修改后（云端持久化！）
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
    # 修改后（云端持久化！）
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username = ? AND password_hash = ?",
              (username, hash_password(password)))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def load_user_conversations(user_id):
    """加载用户所有历史对话"""
    # 修改后（云端持久化！）
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
    # 修改后（云端持久化！）
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
# 2. 初始化 AI
if "ai_engine" not in st.session_state:
    st.session_state.ai_engine = NetworkArchitectAI()

# --- 初始化学习进度计数器 ---
if "weekly_progress_count" not in st.session_state:
    st.session_state.weekly_progress_count = 0  # 初始为 0

# --- 初始化 S1 诊疗室对话历史 ---
if "s1_diagnosis_history" not in st.session_state:
    st.session_state.s1_diagnosis_history = ""  # 初始化为空字符串
# --- 初始化 S3 靶场答案 & 原理追问历史 ---
if "s3_solution_text" not in st.session_state:
    st.session_state.s3_solution_text = ""  # S3 答案记忆
if "deep_inquiry_history" not in st.session_state:
    st.session_state.deep_inquiry_history = ""  # 原理追问记忆
# --- 初始化 S1 历史记录列表 (存储多轮对话) ---
if "s1_chat_history_list" not in st.session_state:
    st.session_state.s1_chat_history_list = []  # 结构: [{'title': 'OSPF...', 'content': '...'}]
if "s1_active_history_index" not in st.session_state:
    st.session_state.s1_active_history_index = None  # None代表当前新对话，数字代表查看特定历史

# --- 初始化 S3 靶场历史记录 ---
if "s3_chat_history_list" not in st.session_state:
    st.session_state.s3_chat_history_list = []  # S3 靶场历史记录列表
if "s3_active_history_index" not in st.session_state:
    st.session_state.s3_active_history_index = None  # S3 当前查看的历史索引

# --- 初始化 深度追问历史记录 ---
if "inquiry_chat_history_list" not in st.session_state:
    st.session_state.inquiry_chat_history_list = []  # 深度追问历史记录列表
if "inquiry_active_history_index" not in st.session_state:
    st.session_state.inquiry_active_history_index = None  # 深度追问当前查看的历史索引

# --- 初始化删除模式状态 ---
if "delete_mode" not in st.session_state:
    st.session_state.delete_mode = False
if "delete_menu" not in st.session_state:
    st.session_state.delete_menu = None

# 3. 侧边栏：个人学习档案
with st.sidebar:
    # 检查是否已登录
    # 替换为以下代码（只保留已登录状态的显示）
    if "user_id" not in st.session_state:
        st.title("⚠️ 未登录")
        st.info("请先登录以使用功能")

    else:
        # 已登录状态：显示用户信息和登出按钮
        st.title(f"👨‍💻 欢迎 {st.session_state.username}")
        if st.button("🚪 退出登录", use_container_width=True):
            # 清除所有用户相关状态
            for key in ["user_id", "username", "s1_chat_history_list",
                        "s3_chat_history_list", "inquiry_chat_history_list"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    # 临时调试：显示保存记录
    if st.session_state.get("debug_save"):
        with st.expander("🔍 保存调试日志"):
            for log in st.session_state.debug_save[-5:]:  # 显示最近5条
                st.text(log)
#===================================================================
    try:
        st.image("xinkecolorlog.png", use_container_width=True)
    except:
        # 万一图片没放对位置，显示一个文字提示，防止报错崩溃
        st.error("⚠️ 请将 xinkeyuanlog.png 复制到项目根目录")
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
            st.session_state.s1_active_history_index = None  # 切换回主视图
            st.session_state.s1_diagnosis_history = ""  # 清空当前屏幕
            st.rerun()  # 强制刷新

        # 2. 循环显示历史记录 (倒序：最新的在上面)
        # enumerate(reversed(...)) 让我们从最新的开始遍历
        for i, chat in enumerate(reversed(st.session_state.s1_chat_history_list)):
            # 计算原始列表中的真实索引
            real_index = len(st.session_state.s1_chat_history_list) - 1 - i

            # 截取标题，太长显示省略号
            display_title = (chat['title'][:10] + '..') if len(chat['title']) > 10 else chat['title']

            # 删除模式下的特殊显示
            if st.session_state.delete_mode and st.session_state.delete_menu == "🔍 网络智能诊断":
                # 删除模式下显示删除按钮
                if st.button(f"❌ {display_title}", key=f"del_s1_{real_index}"):
                    # 1. 从session_state删除
                    deleted_record = st.session_state.s1_chat_history_list.pop(real_index)
                    # 2. 从数据库删除（关键！）
                    if "user_id" in st.session_state:
                        # 修改后（云端持久化！）
                        conn = sqlite3.connect(get_db_path(), check_same_thread=False)
                        c = conn.cursor()
                        # 通过标题+模块+用户精确匹配（实际生产建议用ID）
                        c.execute("""DELETE FROM conversations 
                                        WHERE user_id = ? AND module = 's1' AND title = ?""",
                                  (st.session_state.user_id, deleted_record['title']))
                        conn.commit()
                        conn.close()
                    # 如果当前正在查看被删除的记录，回到当前对话
                    if st.session_state.s1_active_history_index == real_index:
                        st.session_state.s1_active_history_index = None
                    st.rerun()
            else:
                # 点击按钮，切换到对应的历史记录
                # key=f"hist_{real_index}" 保证每个按钮ID唯一，不报错
                if st.button(f"📄 {display_title}", key=f"hist_{real_index}"):
                    st.session_state.s1_active_history_index = real_index
                    st.rerun()

    elif menu == "🎯 自适应实验工场":
        st.markdown("#### 🕒 历史对话")

        # 1. 新建对话按钮
        if st.button("➕ 新建对话", use_container_width=True):
            st.session_state.s3_active_history_index = None  # 切换回主视图
            # 清空当前屏幕的题目和答案
            if "s3_task_text" in st.session_state:
                del st.session_state.s3_task_text
            st.session_state.s3_solution_text = ""
            st.session_state.s3_show_answer = False
            st.rerun()  # 强制刷新

        # 2. 循环显示历史记录 (倒序：最新的在上面)
        for i, chat in enumerate(reversed(st.session_state.s3_chat_history_list)):
            # 计算原始列表中的真实索引
            real_index = len(st.session_state.s3_chat_history_list) - 1 - i

            # 截取标题，太长显示省略号
            display_title = (chat['title'][:10] + '..') if len(chat['title']) > 10 else chat['title']

            # 删除模式下的特殊显示
            if st.session_state.delete_mode and st.session_state.delete_menu == "🎯 自适应实验工场":
                # 删除模式下显示删除按钮
                if st.button(f"❌ {display_title}", key=f"del_s3_{real_index}"):
                    # 1. 从session_state删除
                    deleted_record = st.session_state.s3_chat_history_list.pop(real_index)

                    # 2. 从数据库删除（关键！）
                    if "user_id" in st.session_state:
                        # 修改后（云端持久化！）
                        conn = sqlite3.connect(get_db_path(), check_same_thread=False)
                        c = conn.cursor()
                        # 通过标题+模块+用户精确匹配（实际生产建议用ID）
                        c.execute("""DELETE FROM conversations 
                                        WHERE user_id = ? AND module = 's3' AND title = ?""",
                                  (st.session_state.user_id, deleted_record['title']))
                        conn.commit()
                        conn.close()
                    # 如果当前正在查看被删除的记录，回到当前对话
                    if st.session_state.s3_active_history_index == real_index:
                        st.session_state.s3_active_history_index = None
                    st.rerun()
            else:
                # 点击按钮，切换到对应的历史记录
                if st.button(f"📄 {display_title}", key=f"s3_hist_{real_index}"):
                    st.session_state.s3_active_history_index = real_index
                    st.rerun()

    elif menu == "🧠 协议认知诊断":
        st.markdown("#### 🕒 历史对话")

        # 1. 新建对话按钮
        if st.button("➕ 新建对话", use_container_width=True):
            st.session_state.inquiry_active_history_index = None  # 切换回主视图
            # 清空当前屏幕的追问记录
            st.session_state.deep_inquiry_history = ""
            st.rerun()  # 强制刷新

        # 2. 循环显示历史记录 (倒序：最新的在上面)
        for i, chat in enumerate(reversed(st.session_state.inquiry_chat_history_list)):
            # 计算原始列表中的真实索引
            real_index = len(st.session_state.inquiry_chat_history_list) - 1 - i

            # 截取标题，太长显示省略号
            display_title = (chat['title'][:10] + '..') if len(chat['title']) > 10 else chat['title']

            # 删除模式下的特殊显示
            if st.session_state.delete_mode and st.session_state.delete_menu == "🧠 协议认知诊断":
                # 删除模式下显示删除按钮
                if st.button(f"❌ {display_title}", key=f"del_inquiry_{real_index}"):
                    # 1. 从session_state删除
                    deleted_record = st.session_state.inquiry_chat_history_list.pop(real_index)

                    # 2. 从数据库删除（关键！）
                    if "user_id" in st.session_state:
                        conn = sqlite3.connect('netarchitect.db')
                        c = conn.cursor()
                        # 通过标题+模块+用户精确匹配（实际生产建议用ID）
                        c.execute("""DELETE FROM conversations 
                                        WHERE user_id = ? AND module = 'inquiry' AND title = ?""",
                                  (st.session_state.user_id, deleted_record['title']))
                        conn.commit()
                        conn.close()
                    # 如果当前正在查看被删除的记录，回到当前对话
                    if st.session_state.inquiry_active_history_index == real_index:
                        st.session_state.inquiry_active_history_index = None
                    st.rerun()
            else:
                # 点击按钮，切换到对应的历史记录
                if st.button(f"📄 {display_title}", key=f"inquiry_hist_{real_index}"):
                    st.session_state.inquiry_active_history_index = real_index
                    st.rerun()

    # 显示删除模式提示
    if st.session_state.delete_mode and st.session_state.delete_menu == menu:
        st.warning("⚠️ 已进入删除模式！点击对话标题即可删除。再次点击删除模式按钮退出。")

    # 模拟的用户状态
    # 动态的用户状态
    # 计算百分比 (0 到 1.0 之间)
    current_count = st.session_state.weekly_progress_count
    progress_percent = min(current_count / 10, 1.0)  # 封顶 100%

    st.write(f"**当前状态 (已完成 {current_count}/10 任务)**")
    st.progress(progress_percent, text="本周学习进度")

    if current_count >= 10:
        st.success("🎉 太棒了！本周学习目标已达成！")
    else:
        # 使用自定义HTML显示红色进度条
        st.markdown(f"""
           <div style="background-color: #FFCDD2; border-radius: 4px; padding: 2px;">
               <div style="background-color: #F44336; width: {progress_percent * 100}%; height: 20px; border-radius: 4px; text-align: center; line-height: 20px; color: white; font-size: 12px;">
                   {int(progress_percent * 100)}%
               </div>
           </div>
           """, unsafe_allow_html=True)
        # 新增这行：给学生一点动力
        st.caption(f"加油！再完成 {10 - current_count} 个任务即可达成目标 🚀")

    st.info("💡 提示：多思考，少依赖。先尝试自己分析报错原因。")

# =============== 居中登录界面（插入此处） ===============
if "user_id" not in st.session_state:
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

        if st.session_state.get("show_register", False):
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

        # 关键升级：强制思考环节
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

        # 场景 A：用户刚刚点击了"提交"按钮（生成新内容）
        if analyze_btn:
            if not user_thought:
                st.warning("⚠️ 请先填写你的排查思路！学习不能只靠 AI。")
            elif not user_code:
                st.warning("⚠️ 请粘贴配置代码。")
            else:
                with result_box:
                    with st.chat_message("assistant", avatar="🤖"):
                        st.markdown("#### 🧠 导师正在分析...")
                        # 获取流式响应
                        stream = st.session_state.ai_engine.get_diagnostic_response(user_code, user_thought, topic)

                        # --- 关键修改：st.write_stream 会返回完整的字符串 ---
                        # 我们不仅把它打印出来，还顺手存进 session_state 里
                        response_text = st.write_stream(stream)
                        st.session_state.s1_diagnosis_history = response_text
                        # --- (新增) 自动存档逻辑 ---
                        # 1. 构造标题 (用主题+时间或思路)
                        timestamp = datetime.now().strftime("%H:%M")
                        title = f"[{timestamp}] {topic}"

                        # 2. 存入列表
                        new_record = {"title": title, "content": response_text}
                        st.session_state.s1_chat_history_list.append(new_record)
####################################################################
                        if "user_id" in st.session_state:
                            save_conversation(
                                user_id=st.session_state.user_id,
                                module="s1",
                                title=title,
                                content=response_text
                            )

###########################################################################
                        # 3. 限制只存 10 条 (超过就把最旧的删掉)
                        if len(st.session_state.s1_chat_history_list) > 10:
                            st.session_state.s1_chat_history_list.pop(0)

                        # 4. 重置查看状态为"当前"
                        st.session_state.s1_active_history_index = None
        # 场景 B: 用户点击了侧边栏的历史记录 (查看旧存档)
        elif st.session_state.s1_active_history_index is not None:
            # 根据索引取出历史数据
            record = st.session_state.s1_chat_history_list[st.session_state.s1_active_history_index]
            with result_box:
                with st.chat_message("assistant", avatar="🤖"):
                    # 显示标题提示这是历史
                    st.caption(f"📂 正在查看历史存档：{record['title']}")
                    st.markdown(record["content"])



        # 场景 B：用户没点按钮，但之前有历史记录（切换页面回来后显示）
        elif st.session_state.s1_diagnosis_history:
            with result_box:
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown("#### 🧠 导师的历史分析...")
                    # 直接显示存下来的文字
                    st.markdown(st.session_state.s1_diagnosis_history)
        # 场景 C (新增)：默认初始化状态
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


# ==================== 模块二：今日定制靶场 (S3 升级版) ====================
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

    # --- 核心逻辑修改：引入 Session State 防止刷新丢失 ---

    # 1. 负责生成任务 (当点击生成按钮时)
    if gen_btn and today_focus:
        # 重置答案显示的开关，因为生成了新题
        st.session_state.s3_show_answer = False
        st.session_state.current_task_scored = False  # <--- 新增这行：重置计分状态，允许新任务加分
        st.session_state.s3_solution_text = ""  # <--- 新增：生成新题时，清空旧的答案记忆！
        with st.spinner(f"正在构建关于【{today_focus}】的拓扑环境..."):
            # 调用 AI 生成任务
            stream = st.session_state.ai_engine.generate_personalized_task(today_focus, level)
            # 关键点：st.write_stream 会返回完整的生成文本，我们将它存入 session_state
            # 这样点击"查看答案"刷新页面后，题目文字才不会消失
            st.session_state.s3_task_text = st.write_stream(stream)

            # --- (新增) 自动存档逻辑 ---
            timestamp = datetime.now().strftime("%H:%M")
            title = f"[{timestamp}] {today_focus}"

            # 2. 存入列表
            new_record = {"title": title, "content": st.session_state.s3_task_text, "level": level, "solution": ""}
            st.session_state.s3_chat_history_list.append(new_record)

            if "user_id" in st.session_state:
                save_conversation(
                    user_id=st.session_state.user_id,
                    module="s3",
                    title=title,
                    content=st.session_state.s3_task_text
                )





            # 3. 限制只存 10 条 (超过就把最旧的删掉)
            if len(st.session_state.s3_chat_history_list) > 10:
                st.session_state.s3_chat_history_list.pop(0)

            # 4. 重置查看状态为"当前"
            st.session_state.s3_active_history_index = None

    # 2. 负责显示任务 (添加历史记录查看逻辑)
    # 场景 A: 用户点击了侧边栏的历史记录 (查看旧存档)
    if st.session_state.s3_active_history_index is not None:
        # 根据索引取出历史数据
        record = st.session_state.s3_chat_history_list[st.session_state.s3_active_history_index]
        st.markdown(record["content"])
        st.markdown("---")

        # 显示历史答案（如果有）
        if record.get("solution"):
            st.subheader("📝 历史参考答案与解析")
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(record["solution"])
            # 设置答案已显示标志
            st.session_state.s3_show_answer = True
            st.session_state.s3_solution_text = record["solution"]

    # 2. 负责显示任务 (只要 session 里有题目，就一直显示，不管是刚生成的还是刷新后的)
    elif "s3_task_text" in st.session_state and st.session_state.s3_task_text:
        with st.chat_message("assistant", avatar="🤖"):
             st.markdown(st.session_state.s3_task_text)

    # 3. (新增) 默认初始化状态 - 显示引导框
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

    # 3. 负责显示"查看答案"按钮 (只有存在题目时才显示这个按钮)
    if ("s3_task_text" in st.session_state and st.session_state.s3_task_text) or \
            (st.session_state.s3_active_history_index is not None and
             st.session_state.s3_chat_history_list[st.session_state.s3_active_history_index].get("solution")):
        st.markdown("---")

        # 这是一个开关逻辑：点击按钮，把开关打开
        if st.button("✅ 我做完了，查看参考答案"):
            st.session_state.s3_show_answer = True

            # --- 新增：为了防止重复点击同一个任务刷分，我们可以加一个小锁 ---
            # 如果当前任务还没被计分过，才加分
            if not st.session_state.get("current_task_scored", False):
                if st.session_state.weekly_progress_count < 10:
                    st.session_state.weekly_progress_count += 1
                st.session_state.current_task_scored = True  # 标记为已计分
                st.rerun()  # 强制刷新页面，让侧边栏进度条立刻更新
        # 如果开关是开着的，就显示答案
        if st.session_state.get("s3_show_answer", False):
            st.subheader("📝 参考答案与解析")
            # 场景 A：已经有存下来的答案（切换页面回来的情况），直接显示
            if st.session_state.s3_solution_text:
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(st.session_state.s3_solution_text)

                # --- (新增) 更新历史记录中的答案 ---
                if st.session_state.s3_active_history_index is not None:
                    st.session_state.s3_chat_history_list[st.session_state.s3_active_history_index][
                        "solution"] = st.session_state.s3_solution_text
            # 场景 B：这是第一次点查看（内存是空的），需要生成并存储
            else:
                with st.spinner("AI 正在撰写解题思路..."):
                    with st.chat_message("assistant", avatar="🤖"):
                        ans_stream = st.session_state.ai_engine.generate_task_solution(
                            st.session_state.s3_task_text)
                        # 重点：生成完立刻存进去
                        st.session_state.s3_solution_text = st.write_stream(ans_stream)

                # --- (新增) 更新历史记录中的答案 ---
                if st.session_state.s3_active_history_index is not None:
                    st.session_state.s3_chat_history_list[st.session_state.s3_active_history_index][
                        "solution"] = st.session_state.s3_solution_text
                elif len(st.session_state.s3_chat_history_list) > 0:
                    # 如果当前是最新任务，更新最后一条记录
                    st.session_state.s3_chat_history_list[-1]["solution"] = st.session_state.s3_solution_text


# ==================== 模块三：原理深度追问 (新增) ====================
elif menu == "🧠 协议认知诊断":
    st.header("🧠 协议认知诊断引擎 | 深度原理探析")
    st.markdown("不写代码，只聊原理。用苏格拉底的方式检验你的理解深度。")

    concept = st.text_input("输入一个让你困惑的概念", placeholder="例如：为什么 TCP 需要三次握手？")

    # 场景 A：点击按钮生成新对话
    if st.button("开始追问"):
        if concept:
            with st.chat_message("assistant", avatar="🤖"):
                stream = st.session_state.ai_engine.socratic_quiz(concept)
                # 重点：存入记忆
                response_text = st.write_stream(stream)
                st.session_state.deep_inquiry_history = response_text

            # --- (新增) 自动存档逻辑 ---
            timestamp = datetime.now().strftime("%H:%M")
            title = f"[{timestamp}] {concept}"

            # 存入列表
            new_record = {"title": title, "content": response_text}
            st.session_state.inquiry_chat_history_list.append(new_record)
#################################################################################
            if "user_id" in st.session_state:
                save_conversation(
                    user_id=st.session_state.user_id,
                    module="inquiry",
                    title=title,
                    content=response_text
                )
###################################################################################
            # 限制只存 10 条 (超过就把最旧的删掉)
            if len(st.session_state.inquiry_chat_history_list) > 10:
                st.session_state.inquiry_chat_history_list.pop(0)

            # 重置查看状态为"当前"
            st.session_state.inquiry_active_history_index = None
        else:
            st.error("请输入概念名称")

    # 场景 B: 用户点击了侧边栏的历史记录 (查看旧存档)
    elif st.session_state.inquiry_active_history_index is not None:
        # 根据索引取出历史数据
        record = st.session_state.inquiry_chat_history_list[st.session_state.inquiry_active_history_index]

        with st.chat_message("assistant", avatar="🤖"):
            # 显示标题提示这是历史
            st.caption(f"📂 正在查看历史存档：{record['title']}")
            st.markdown(record["content"])

    # 场景 B：没点按钮，但有历史记录（切换页面回来的情况）
    elif st.session_state.deep_inquiry_history:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(st.session_state.deep_inquiry_history)
    # 场景 C (新增)：默认初始化状态
    # 当没有点击按钮，且没有历史记录时，显示一个白色的空回答框（引导框）
    else:
        with st.chat_message("assistant", avatar="🤖"):
            # 这个框是白色的（由之前的CSS决定），且高度会根据文字自动适应
            st.markdown("""
                👋 **你好！我是你的原理导师。**

                请在上方输入你想要深入理解的网络概念（如 OSPF、ARP、TCP等），
                我会用苏格拉底式教学法带你从原理层面攻克它！🚀
                """)