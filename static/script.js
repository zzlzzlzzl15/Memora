// 全局API基础URL
const apiBaseUrl = window.location.origin;

document.addEventListener('DOMContentLoaded', () => {
    console.log('apiBaseUrl:', apiBaseUrl);
    // 优先尝试加载用户提供的自定义 logo
    tryLoadCustomLogo();

    // ========== 语言切换功能 ==========
    let currentLang = localStorage.getItem('language') || 'zh';
    
    const translations = {
        zh: {
            // App UI
            documentsTitle: '文档',
            openTrash: '回收站',
            docPreview: '文档预览',
            back: '返回',
            uploadFormTitle: '上传文档',
            uploadButton: '上传',
            documentTitlePlaceholder: '文档标题',
            trashTitle: '回收站',
            backFromTrash: '返回文档',
            tabQueryTitle: '知识查询',
            tabOrganizeTitle: '知识梳理',
            historyToggleTitle: '打开历史',
            uploadSource: '上传来源',
            chatPlaceholder: '输入问题，例如：总结最近上传的文档要点',
            sendButton: '发送',
            studioTitle: '工作室',
            audioTitle: '音频预览',
            audioDesc: '预留功能，后续开放',
            mindmapTitle: '思维导图',
            mindmapDesc: '预留功能，后续开放',
            reportTitle: '报告生成',
            reportDesc: '预留功能，后续开放',
            moreTitle: '更多',
            moreDesc: '模块位占位',
            historyTitle: '历史记录',
            newChat: '新建对话',
            statsTitle: '使用统计',
            statsMonthLabel: '选择月份',
            statsGridAria: '使用统计贡献图',
            statsTotalQueries: '查询总数',
            statsTotalAdded: '新增文档',
            statsTotalDeleted: '删除文档',
            statsActiveDays: '活跃天数',
            statsLegendLabel: '活跃度：'
        ,
            // 登录表单
            loginUsername: '用户名或邮箱',
            loginPassword: '密码',
            loginBtn: '登录',
            forgotUsernameLabel: '忘记用户名？',
            forgotUsername: '邮箱登录',
            otpLogin: '验证码登录',
            loginFooterText: '没有账户？',
            registerHere: '立即注册',
            // 验证码登录
            otpPhone: '手机号码',
            otpCode: '输入邮箱验证码',
            getOtp: '获取验证码',
            backToLogin: '返回密码登录',
            // 邮箱验证码登录
            emailOtpEmail: '邮箱地址',
            emailOtpCode: '验证码',
            sendEmailOtp: '发送验证码',
            emailOtpLoginBtn: '登录',
            backToLoginFromEmailOtp: '返回密码登录',
            // 注册表单
            registerUsername: '用户名',
            registerEmail: '邮箱地址',
            registerPassword: '设置密码',
            registerBtn: '立即注册',
            registerFooterText: '已有账户？',
            loginHere: '立即登录',
        },
        en: {
            // App UI
            documentsTitle: 'Documents',
            openTrash: 'Recycle Bin',
            docPreview: 'Document Preview',
            back: 'Back',
            uploadFormTitle: 'Upload Document',
            uploadButton: 'Upload',
            documentTitlePlaceholder: 'Document Title',
            trashTitle: 'Recycle Bin',
            backFromTrash: 'Back to Documents',
            tabQueryTitle: 'Knowledge Search',
            tabOrganizeTitle: 'Knowledge Organize',
            historyToggleTitle: 'Open History',
            uploadSource: 'Upload Source',
            chatPlaceholder: 'Enter a question, e.g., summarize recent uploaded documents',
            sendButton: 'Send',
            studioTitle: 'Studio',
            audioTitle: 'Audio Preview',
            audioDesc: 'Coming soon',
            mindmapTitle: 'Mind Map',
            mindmapDesc: 'Coming soon',
            reportTitle: 'Report Generation',
            reportDesc: 'Coming soon',
            moreTitle: 'More',
            moreDesc: 'Placeholder module',
            historyTitle: 'History',
            newChat: 'New Chat',
            statsTitle: 'Usage Statistics',
            statsMonthLabel: 'Select month',
            statsGridAria: 'Usage contribution chart',
            statsTotalQueries: 'Total Queries',
            statsTotalAdded: 'Documents Added',
            statsTotalDeleted: 'Documents Deleted',
            statsActiveDays: 'Active Days',
            statsLegendLabel: 'Activity:'
        ,
            // Login form
            loginUsername: 'Username or Email',
            loginPassword: 'Password',
            loginBtn: 'Login',
            forgotUsernameLabel: 'Forgot username?',
            forgotUsername: 'Email login',
            otpLogin: 'OTP Login',
            loginFooterText: "Don't have an account?",
            registerHere: 'Register here',
            // OTP login
            otpPhone: 'Phone Number',
            otpCode: 'Enter Email OTP',
            getOtp: 'Get OTP',
            backToLogin: 'Back to Login',
            // Email OTP login
            emailOtpEmail: 'Email Address',
            emailOtpCode: 'Verification Code',
            sendEmailOtp: 'Send Code',
            emailOtpLoginBtn: 'Login',
            backToLoginFromEmailOtp: 'Back to Password Login',
            // Register form
            registerUsername: 'Username',
            registerEmail: 'Email Address',
            registerPassword: 'Password',
            registerBtn: 'Register',
            registerFooterText: 'Already have an account?',
            loginHere: 'Login here',
        }
    };

    function updateLanguage(lang) {
        currentLang = lang;
        localStorage.setItem('language', lang);
        const t = translations[lang];
        
        // 更新登录表单
        const loginUsernameEl = document.getElementById('login-username');
        if (loginUsernameEl) loginUsernameEl.placeholder = t.loginUsername;
        const loginPasswordEl = document.getElementById('login-password');
        if (loginPasswordEl) loginPasswordEl.placeholder = t.loginPassword;
        const loginBtnEl = document.getElementById('login-btn');
        if (loginBtnEl) loginBtnEl.textContent = t.loginBtn;
        const forgotUsernameLabelEl = document.querySelector('.auth-switches .forgot-text:not(#forgot-username)');
        if (forgotUsernameLabelEl) forgotUsernameLabelEl.textContent = t.forgotUsernameLabel;
        const forgotUsernameEl = document.getElementById('forgot-username');
        if (forgotUsernameEl) forgotUsernameEl.textContent = t.forgotUsername;
        const showLoginOtpEl = document.getElementById('show-login-otp');
        if (showLoginOtpEl) showLoginOtpEl.textContent = t.otpLogin;
        const loginFooterTextEl = document.getElementById('login-footer-text');
        if (loginFooterTextEl) loginFooterTextEl.textContent = t.loginFooterText;
        const showRegisterEl = document.getElementById('show-register');
        if (showRegisterEl) showRegisterEl.textContent = t.registerHere;
        
        // 更新验证码登录表单
        const otpPhoneEl = document.getElementById('otp-phone');
        if (otpPhoneEl) otpPhoneEl.placeholder = t.otpPhone;
        const otpCodeEl = document.getElementById('otp-code');
        if (otpCodeEl) otpCodeEl.placeholder = t.otpCode;
        const sendOtpBtnEl = document.getElementById('send-otp-btn');
        if (sendOtpBtnEl) sendOtpBtnEl.textContent = t.getOtp;
        const loginOtpBtnEl = document.getElementById('login-otp-btn');
        if (loginOtpBtnEl) loginOtpBtnEl.textContent = t.loginBtn;
        const backToLoginEl = document.getElementById('back-to-login');
        if (backToLoginEl) backToLoginEl.textContent = t.backToLogin;
        
        // 更新邮箱验证码登录表单
        const emailOtpEmailEl = document.getElementById('email-otp-email');
        if (emailOtpEmailEl) emailOtpEmailEl.placeholder = t.emailOtpEmail;
        const emailOtpCodeEl = document.getElementById('email-otp-code');
        if (emailOtpCodeEl) emailOtpCodeEl.placeholder = t.emailOtpCode;
        const sendEmailOtpBtnEl = document.getElementById('send-email-otp-btn');
        if (sendEmailOtpBtnEl) sendEmailOtpBtnEl.textContent = t.sendEmailOtp;
        const emailOtpLoginBtnEl = document.getElementById('email-otp-login-btn');
        if (emailOtpLoginBtnEl) emailOtpLoginBtnEl.textContent = t.emailOtpLoginBtn;
        const backToLoginFromEmailOtpEl = document.getElementById('back-to-login-from-email-otp');
        if (backToLoginFromEmailOtpEl) backToLoginFromEmailOtpEl.textContent = t.backToLoginFromEmailOtp;
        
        // 更新注册表单
        const registerUsernameEl = document.getElementById('register-username');
        if (registerUsernameEl) registerUsernameEl.placeholder = t.registerUsername;
        const registerEmailEl = document.getElementById('register-email');
        if (registerEmailEl) registerEmailEl.placeholder = t.registerEmail;
        const registerPasswordEl = document.getElementById('register-password');
        if (registerPasswordEl) registerPasswordEl.placeholder = t.registerPassword;
        const registerOtpCodeEl = document.getElementById('register-otp-code');
        if (registerOtpCodeEl) registerOtpCodeEl.placeholder = t.otpCode;
        const sendRegisterOtpBtnEl = document.getElementById('send-register-otp-btn');
        if (sendRegisterOtpBtnEl) sendRegisterOtpBtnEl.textContent = t.getOtp;
        const registerBtnEl = document.getElementById('register-btn');
        if (registerBtnEl) registerBtnEl.textContent = t.registerBtn;
        const registerFooterTextEl = document.getElementById('register-footer-text');
        if (registerFooterTextEl) registerFooterTextEl.textContent = t.registerFooterText;
        const showLoginEl = document.getElementById('show-login');
        if (showLoginEl) showLoginEl.textContent = t.loginHere;
        
        // 更新知识库主界面
        const docsTitleEl = document.getElementById('docs-title');
        if (docsTitleEl) docsTitleEl.textContent = t.documentsTitle;
        const openTrashBtnEl = document.getElementById('open-trash-btn');
        if (openTrashBtnEl) openTrashBtnEl.textContent = t.openTrash;
        const docPreviewEl = document.getElementById('doc-view-title');
        if (docPreviewEl) docPreviewEl.textContent = t.docPreview;
        const backBtnEl = document.getElementById('back-to-docs-btn');
        if (backBtnEl) backBtnEl.textContent = t.back;
        const uploadFormTitleEl = document.getElementById('upload-form-title');
        if (uploadFormTitleEl) uploadFormTitleEl.textContent = t.uploadFormTitle;
        const documentTitleEl = document.getElementById('document-title');
        if (documentTitleEl) documentTitleEl.placeholder = t.documentTitlePlaceholder;
        const uploadBtnEl = document.getElementById('upload-btn');
        if (uploadBtnEl) uploadBtnEl.textContent = t.uploadButton;
        const trashTitleEl = document.getElementById('trash-title');
        if (trashTitleEl) trashTitleEl.textContent = t.trashTitle;
        const backFromTrashBtnEl = document.getElementById('back-to-docs-from-trash-btn');
        if (backFromTrashBtnEl) backFromTrashBtnEl.textContent = t.backFromTrash;
        const tabQueryEl = document.getElementById('tab-query');
        if (tabQueryEl) tabQueryEl.textContent = t.tabQueryTitle;
        const tabOrganizeEl = document.getElementById('tab-organize');
        if (tabOrganizeEl) tabOrganizeEl.textContent = t.tabOrganizeTitle;
        const histToggle = document.getElementById('history-toggle');
        if (histToggle) { histToggle.title = t.historyToggleTitle; histToggle.setAttribute('aria-label', t.historyToggleTitle); }
        const uploadSourceBtnEl = document.getElementById('upload-source-btn');
        if (uploadSourceBtnEl) uploadSourceBtnEl.textContent = t.uploadSource;
        const chatMessageEl = document.getElementById('chat-message');
        if (chatMessageEl) chatMessageEl.placeholder = t.chatPlaceholder;
        const sendChatBtnEl = document.getElementById('send-chat-btn');
        if (sendChatBtnEl) sendChatBtnEl.textContent = t.sendButton;
        const studioTitleEl = document.getElementById('studio-title');
        if (studioTitleEl) studioTitleEl.textContent = t.studioTitle;
        const audioTitleEl = document.getElementById('audio-title'); if (audioTitleEl) audioTitleEl.textContent = t.audioTitle;
        const audioDescEl = document.getElementById('audio-desc'); if (audioDescEl) audioDescEl.textContent = t.audioDesc;
        const mindmapTitleEl = document.getElementById('mindmap-title'); if (mindmapTitleEl) mindmapTitleEl.textContent = t.mindmapTitle;
        const mindmapDescEl = document.getElementById('mindmap-desc'); if (mindmapDescEl) mindmapDescEl.textContent = t.mindmapDesc;
        const reportTitleEl = document.getElementById('report-title'); if (reportTitleEl) reportTitleEl.textContent = t.reportTitle;
        const reportDescEl = document.getElementById('report-desc'); if (reportDescEl) reportDescEl.textContent = t.reportDesc;
        const moreTitleEl = document.getElementById('more-title'); if (moreTitleEl) moreTitleEl.textContent = t.moreTitle;
        const moreDescEl = document.getElementById('more-desc'); if (moreDescEl) moreDescEl.textContent = t.moreDesc;
        const statsTitleEl = document.getElementById('stats-title'); if (statsTitleEl) statsTitleEl.textContent = '📊 ' + t.statsTitle;
        const statsMonthLabelEl = document.getElementById('stats-month-label'); if (statsMonthLabelEl) statsMonthLabelEl.textContent = t.statsMonthLabel;
        const statsGridEl = document.getElementById('stats-grid'); if (statsGridEl) statsGridEl.setAttribute('aria-label', t.statsGridAria);
        
        // 更新统计概览标签
        const statsSummaryItems = document.querySelectorAll('.stats-summary-label');
        if (statsSummaryItems.length >= 4) {
            statsSummaryItems[0].textContent = t.statsTotalQueries;
            statsSummaryItems[1].textContent = t.statsTotalAdded;
            statsSummaryItems[2].textContent = t.statsTotalDeleted;
            statsSummaryItems[3].textContent = t.statsActiveDays;
        }
        
        // 更新图例标签
        const legendLabel = document.querySelector('.stats-legend > span');
        if (legendLabel) legendLabel.textContent = t.statsLegendLabel;
        
        // 更新下拉菜单语言选项加粗状态
        const menuLangZh = document.getElementById('menu-lang-zh');
        const menuLangEn = document.getElementById('menu-lang-en');
        if (menuLangZh && menuLangEn) {
            menuLangZh.classList.toggle('active', lang === 'zh');
            menuLangEn.classList.toggle('active', lang === 'en');
        }
        // 顶部登录页语言按钮的加粗状态
        const langZh = document.getElementById('lang-zh');
        const langEn = document.getElementById('lang-en');
        if (langZh && langEn) {
            langZh.classList.toggle('active', lang === 'zh');
            langEn.classList.toggle('active', lang === 'en');
        }
        // 下拉菜单语言对勾显示
        const zhCheck = document.getElementById('menu-lang-zh-check');
        const enCheck = document.getElementById('menu-lang-en-check');
        if (zhCheck && enCheck) {
            zhCheck.style.display = lang === 'zh' ? 'inline' : 'none';
            enCheck.style.display = lang === 'en' ? 'inline' : 'none';
        }
    }

    // 顶部登录页语言按钮事件
    const langToggleBtn = document.getElementById('lang-toggle-btn');
    langToggleBtn?.addEventListener('click', () => {
        const newLang = currentLang === 'zh' ? 'en' : 'zh';
        updateLanguage(newLang);
    });
    // 初始化语言
    updateLanguage(currentLang);

    // ========== 通用工具函数 ==========
    
    /**
     * 解析UTC时间字符串（后端返回的时间可能没有Z后缀）
     * @param {string} utcTimeStr - UTC时间字符串
     * @returns {Date} - JavaScript Date对象（自动转换为本地时区）
     */
    function parseUTCTime(utcTimeStr) {
        if (!utcTimeStr) return new Date();
        
        // 如果已经有Z后缀，直接解析
        if (utcTimeStr.endsWith('Z')) {
            return new Date(utcTimeStr);
        }
        
        // 如果有明确的时区偏移（+08:00 或 -05:00），直接解析
        if (/[+-]\d{2}:\d{2}$/.test(utcTimeStr)) {
            return new Date(utcTimeStr);
        }
        
        // 否则，认为是UTC时间，添加Z后缀
        // 支持格式：2025-11-18T08:02:35.217420 或 2025-11-18 08:02:35.217420
        return new Date(utcTimeStr + 'Z');
    }
    
    /**
     * 格式化时间为相对时间或绝对时间
     * @param {string} utcTimeStr - UTC时间字符串
     * @returns {string} - 格式化后的时间文本
     */
    function formatRelativeTime(utcTimeStr) {
        const date = parseUTCTime(utcTimeStr);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        
        if (diffMins < 1) return '刚刚';
        if (diffMins < 60) return `${diffMins}分钟前`;
        if (diffMins < 1440) return `${Math.floor(diffMins / 60)}小时前`;
        if (diffMins < 10080) {
            const days = Math.floor(diffMins / 1440);
            return `${days}天前`;
        }
        // 超过7天，显示完整日期时间
        return date.toLocaleString('zh-CN', { 
            month: '2-digit', 
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    // Auth elements
    const authContainer = document.getElementById('auth-container');
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const emailOtpLoginForm = document.getElementById('email-otp-login-form');
    const loginBtn = document.getElementById('login-btn');
    const registerBtn = document.getElementById('register-btn');
    const showRegister = document.getElementById('show-register');
    const showLogin = document.getElementById('show-login');
    const backToLoginFromEmailOtp = document.getElementById('back-to-login-from-email-otp');
    const emailOtpLoginBtn = document.getElementById('email-otp-login-btn');
    const sendRegisterOtpBtn = document.getElementById('send-register-otp-btn');
    const sendEmailOtpBtn = document.getElementById('send-email-otp-btn');

    // Main container elements
    const mainContainer = document.getElementById('main-container');
    const userAvatar = document.getElementById('user-avatar');
    const avatarText = document.getElementById('avatar-text');
    const userDropdown = document.getElementById('user-dropdown');
    const dropdownUsername = document.getElementById('dropdown-username');
    const menuLogout = document.getElementById('menu-logout');
    const menuStatistics = document.getElementById('menu-statistics');

    // Document management elements
    const documentList = document.getElementById('document-list');
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('file-input');
    const documentTitle = document.getElementById('document-title');
    const uploadBtn = document.getElementById('upload-btn');
    const openTrashBtn = document.getElementById('open-trash-btn');

    // Trash management elements
    const trashManagement = document.getElementById('trash-management');
    const deletedDocumentList = document.getElementById('deleted-document-list');
    const backToDocsFromTrashBtn = document.getElementById('back-to-docs-from-trash-btn');

    // Document viewer elements
    const documentViewer = document.getElementById('document-viewer');
    const docViewTitle = document.getElementById('doc-view-title');
    const docViewContent = document.getElementById('doc-view-content');
    const backToDocsBtn = document.getElementById('back-to-docs-btn');

    // Chat elements
    const chatWindow = document.getElementById('chat-window');
    const chatMessage = document.getElementById('chat-message');
    const sendChatBtn = document.getElementById('send-chat-btn');
    // 当前模式：false=知识查询；true=知识梳理
    let isOrganizeMode = false;
    // Mode tabs (title choices)
    const tabQuery = document.getElementById('tab-query');
    const tabOrganize = document.getElementById('tab-organize');
    // Source modal elements
    const uploadSourceBtn = document.getElementById('upload-source-btn');
    const sourceModal = document.getElementById('source-modal');
    const sourceModalClose = document.getElementById('source-modal-close');
    const tabUrlBtn = document.getElementById('tab-url');
    const tabFileBtn = document.getElementById('tab-file');
    const tabUrlBody = document.getElementById('tab-url-body');
    const tabFileBody = document.getElementById('tab-file-body');
    const sourceUrlInput = document.getElementById('source-url-input');
    // 记录最近一次抓取来源，便于保存知识时附带元数据
    let currentSourceMeta = { url: null, title: null };
    const sourceUrlTitle = document.getElementById('source-url-title');
    const submitUrlBtn = document.getElementById('submit-url-btn');
    const urlCrawlProgress = document.getElementById('url-crawl-progress');
    const urlCrawlProgressBar = document.getElementById('url-crawl-progress-bar');
    const urlCrawlProgressLabel = document.getElementById('url-crawl-progress-label');
    const sourceFileInput = document.getElementById('source-file-input');
    const sourceFileTitle = document.getElementById('source-file-title');
    const submitFileBtn = document.getElementById('submit-file-btn');
    // 历史按钮与面板
    const historyToggle = document.getElementById('history-toggle');
    const historyPanel = document.getElementById('history-panel');
    // 会话ID：区分两种模式
    let currentQuerySessionId = null;
    let currentOrganizeSessionId = null;
    let currentStreamController = null;

    // --- 会话与历史：前端管理 ---
    async function ensureActiveSession(mode) {
        const token = localStorage.getItem('token');
        if (!token) return null;
        const safeMode = mode === 'organize' ? 'organize' : 'query';
        try {
            const resp = await fetch(`${apiBaseUrl}/api/v1/conversations/history?mode=${safeMode}&limit=100`, {
                method: 'GET',
                headers: { 'Authorization': `Bearer ${token}` },
                cache: 'no-store'
            });
            if (!resp.ok) {
                console.warn('ensureActiveSession failed:', resp.status);
                return null;
            }
            const data = await resp.json();
            const sid = data?.session?.session_id || null;
            if (safeMode === 'query') currentQuerySessionId = sid; else currentOrganizeSessionId = sid;
            return sid;
        } catch (e) {
            console.warn('ensureActiveSession error:', e);
            return null;
        }
    }

    async function closeActiveSessions() {
        const token = localStorage.getItem('token');
        if (!token) return;
        const toClose = [currentQuerySessionId, currentOrganizeSessionId].filter(Boolean);
        for (const sid of toClose) {
            try {
                await fetch(`${apiBaseUrl}/api/v1/conversations/session/close`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    keepalive: true,
                    body: JSON.stringify({ session_id: sid })
                });
            } catch (e) { console.warn('close session error:', e); }
        }
        currentQuerySessionId = null;
        currentOrganizeSessionId = null;
    }

    async function saveMessage(sessionId, role, content, mode) {
        const token = localStorage.getItem('token');
        if (!token || !sessionId) return null;
        const safeMode = mode === 'organize' ? 'organize' : 'query';
        try {
            const resp = await fetch(`${apiBaseUrl}/api/v1/conversations/message`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ mode: safeMode, session_id: sessionId, role, content })
            });
            if (!resp.ok) {
                let msg = '';
                try { msg = (await resp.json())?.detail || ''; } catch (_) {}
                console.warn(`保存消息失败：${msg || resp.status}`);
                return null;
            }
            return await resp.json();
        } catch (e) {
            console.warn('saveMessage error:', e);
            return null;
        }
    }

    // 已删除旧的 loadHistory 函数，现在使用 loadSessionList 更好地展示会话列表

    // 新增：加载所有会话列表并渲染至历史面板（不区分模式，显示首问20字摘要）
    async function loadSessionList() {
        const token = localStorage.getItem('token');
        if (!token) return [];
        try {
            // 不传 mode 参数，返回所有模式的会话
            const resp = await fetch(`${apiBaseUrl}/api/v1/conversations/sessions?limit=50`, {
                method: 'GET',
                headers: { 'Authorization': `Bearer ${token}` },
                cache: 'no-store'
            });
            if (!resp.ok) {
                console.warn('loadSessionList failed:', resp.status);
                return [];
            }
            const data = await resp.json();
            const sessions = data?.sessions || [];
            
            // 保持降序（最新在前）- 不需要反转
            // sessions.reverse();  // 删除反转操作

            const historyPanel = document.getElementById('history-panel');
            const t = translations[currentLang];
            if (!historyPanel) return sessions;
            
            // 清理历史面板，避免重复创建（先清空所有内容）
            historyPanel.innerHTML = '';
            
            // 创建面板头部
            const header = document.createElement('div');
            header.className = 'history-panel-header';
            header.innerHTML = `
                <div class="history-panel-title">
                    <span>📚</span>
                    <span>${t.historyTitle}</span>
                </div>
                <button class="history-panel-close" title="${t.back}">&times;</button>
            `;
            historyPanel.appendChild(header);
            
            // 绑定关闭按钮事件
            const closeBtn = header.querySelector('.history-panel-close');
            closeBtn.addEventListener('click', () => {
                historyPanel.style.display = 'none';
                historyPanel.setAttribute('aria-hidden', 'true');
            });
            
            // 创建内容容器
            const contentContainer = document.createElement('div');
            contentContainer.className = 'history-panel-content';
            historyPanel.appendChild(contentContainer);
            
            // 在列表顶部添加"新建对话"按钮
            const newChatBtn = document.createElement('button');
            newChatBtn.className = 'new-chat-btn';
            /* t already defined above */
            newChatBtn.innerHTML = `<span>+</span><span>${t.newChat}</span>`;
            newChatBtn.addEventListener('click', async () => {
                // 移除所有历史项的选中状态（确保从整个历史面板查找）
                const historyPanel = document.getElementById('history-panel');
                if (historyPanel) {
                    const allItems = historyPanel.querySelectorAll('.history-item');
                    allItems.forEach(i => i.classList.remove('selected'));
                }
                
                // 清空当前对话窗口（保留历史按钮和面板）
                if (chatWindow) {
                    const messages = chatWindow.querySelectorAll('.chat-message');
                    messages.forEach(msg => msg.remove());
                }
                // 清空当前模式的 sessionId，等待用户发送消息时再创建
                if (isOrganizeMode) {
                    currentOrganizeSessionId = null;
                } else {
                    currentQuerySessionId = null;
                }
                // 关闭历史面板
                historyPanel.style.display = 'none';
                historyPanel.setAttribute('aria-hidden', 'true');
                // 聚焦输入框
                if (chatMessage) chatMessage.focus();
            });
            contentContainer.appendChild(newChatBtn);

            if (!sessions.length) {
                const empty = document.createElement('div');
                empty.className = 'empty';
                empty.textContent = (currentLang === 'zh' ? '暂无历史会话' : 'No history sessions');
                contentContainer.appendChild(empty);
                return sessions;
            }

            // 渲染会话列表（最新在上）
            sessions.forEach((s) => {
                    const item = document.createElement('div');
                    item.className = 'history-item';
                    if (s.is_active) item.classList.add('active');
                    item.setAttribute('tabindex', '0');
                    item.setAttribute('role', 'button');
                    
                    const title = s.preview || '(空会话)';
                    const activeBadge = s.is_active ? '<span class="badge">当前</span>' : '';
                    const mode = s.mode;  // 从会话数据中获取模式
                    
                    // 使用通用函数格式化时间
                    const timeText = formatRelativeTime(s.updated_at);
                    
                    item.innerHTML = `
                        <div class="role">
                            <span>${mode === 'organize' ? '🧠 梳理' : '🔍 查询'}</span>
                            ${activeBadge}
                        </div>
                        <div class="content">${title}</div>
                        <div class="meta">
                            <span>🕒 ${timeText}</span>
                        </div>
                    `;

                    const go = async () => {
                        try {
                            // 移除所有历史项的选中状态和活动状态（确保从整个历史面板查找）
                            const historyPanel = document.getElementById('history-panel');
                            if (historyPanel) {
                                const allItems = historyPanel.querySelectorAll('.history-item');
                                allItems.forEach(i => {
                                    i.classList.remove('selected');
                                    i.classList.remove('active');
                                });
                            }
                            // 添加当前项的选中状态
                            item.classList.add('selected');
                            
                            // 点击会话时自动切换到对应模式
                            setMode(mode === 'organize');
                            
                            // 激活会话（使其成为该模式当前会话）
                            const act = await fetch(`${apiBaseUrl}/api/v1/conversations/session/activate`, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'Authorization': `Bearer ${token}`
                                },
                                body: JSON.stringify({ session_id: s.session_id, mode: mode })
                            });
                            if (!act.ok) { console.warn('activate failed', act.status); }

                            // 更新当前会话ID到内存
                            if (mode === 'organize') {
                                currentOrganizeSessionId = s.session_id;
                            } else {
                                currentQuerySessionId = s.session_id;
                            }

                            // 拉取该会话的消息列表并回放
                            const msgsResp = await fetch(`${apiBaseUrl}/api/v1/conversations/session/${s.session_id}/messages?limit=200`, {
                                method: 'GET',
                                headers: { 'Authorization': `Bearer ${token}` }
                            });
                            let msgs = [];
                            if (msgsResp.ok) { msgs = await msgsResp.json(); }
                            await renderConversationFromHistory(msgs, mode);

                            // 不再自动关闭历史面板，让用户手动控制
                            // historyPanel.style.display = 'none';
                            // historyPanel.setAttribute('aria-hidden', 'true');
                        } catch (e) { console.warn('enter session error', e); }
                    };
                    item.addEventListener('click', go);
                    item.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); }
                    });
                    contentContainer.appendChild(item);
                });
            
            return sessions;
        } catch (e) {
            console.warn('loadSessionList error:', e);
            return [];
        }
    }

    // 从历史消息渲染到聊天窗口，支持继续聊天
    async function renderConversationFromHistory(messages, mode) {
        try {
            const chatWindow = document.getElementById('chat-window');
            if (!chatWindow) return null;
            
            // 保留历史按钮和面板，只清空消息
            const existingMessages = chatWindow.querySelectorAll('.chat-message');
            existingMessages.forEach(msg => msg.remove());

            for (const msg of messages || []) {
                const role = msg.role;
                const content = msg.content || '';
                if (role === 'user') {
                    appendMessage(content, 'user');  // 修正：参数顺序为 (content, sender)
                } else {
                    // 历史不包含来源，这里传空数组以保持UI一致
                    renderBotAnswerWithSources(content, []);
                }
            }
            // 不再创建会话，只聚焦输入框
            const chatInput = document.getElementById('chat-input');
            if (chatInput) chatInput.focus();
            return null;
        } catch (e) {
            console.error('renderConversationFromHistory error:', e);
            return null;
        }
    }

    function tryLoadCustomLogo() {
        const logoEl = document.querySelector('.brand-logo');
        if (!logoEl) return;
        logoEl.src = '/static/logo.svg';
    }

    // Login/Register form switching
    showRegister.addEventListener('click', (e) => {
        e.preventDefault();
        loginForm.style.display = 'none';
        registerForm.style.display = 'block';
        emailOtpLoginForm.style.display = 'none';
    });

    showLogin.addEventListener('click', (e) => {
        e.preventDefault();
        registerForm.style.display = 'none';
        loginForm.style.display = 'block';
        emailOtpLoginForm.style.display = 'none';
    });

    backToLoginFromEmailOtp?.addEventListener('click', (e) => {
        e.preventDefault();
        console.log('返回登录表单链接被点击');
        loginForm.style.display = 'block';
        registerForm.style.display = 'none';
        emailOtpLoginForm.style.display = 'none';
    });

    sendRegisterOtpBtn?.addEventListener('click', (e) => { e.preventDefault(); sendRegisterOtp(); });
    sendEmailOtpBtn?.addEventListener('click', (e) => { e.preventDefault(); sendEmailOtp(); });
    emailOtpLoginBtn?.addEventListener('click', (e) => { e.preventDefault(); loginByEmailOtp(); });

    // 添加并发保护状态
    let isRegistering = false;
    let isLoggingIn = false;

    // --- API Functions ---

    async function registerUser() {
        if (isRegistering) {
            alert('正在注册，请稍候…');
            return;
        }
        isRegistering = true;
        registerBtn.disabled = true;

        const username = document.getElementById('register-username').value;
        const phone_number = document.getElementById('register-phone').value.trim() || null;
        const email = document.getElementById('register-email').value;
        const password = document.getElementById('register-password').value;
        const otpCode = document.getElementById('register-otp-code').value.trim();

        if (!email || !otpCode) {
            alert('请填写邮箱并获取验证码');
            isRegistering = false;
            registerBtn.disabled = false;
            return;
        }

        const controller = new AbortController();
        const timeoutMs = 30000; // 30秒超时
        const timer = setTimeout(() => controller.abort(new DOMException('timeout', 'AbortError')), timeoutMs);

        try {
            console.log('Register: sending request', { username, email, url: `${apiBaseUrl}/api/v1/auth/register` });
            const response = await fetch(`${apiBaseUrl}/api/v1/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, phone_number, email, password, is_active: true, otp_code: otpCode }),
                signal: controller.signal,
                keepalive: true
            });
            console.log('Register: response status', response.status);

            if (response.ok) {
                alert('注册成功！请使用该账户登录。');
                // 切换到登录页并填充用户名/密码，便于直接登录
                document.getElementById('login-username').value = username;
                document.getElementById('login-password').value = password;
                showLogin.click();
            } else {
                let detail = '';
                try { detail = (await response.json())?.detail || ''; } catch (_) {}
                if (typeof detail === 'string' && (detail.includes('用户名') && detail.includes('已存在'))) {
                    alert('该用户名已存在，请更换用户名或直接登录。');
                } else if (typeof detail === 'string' && (detail.includes('邮箱') && detail.includes('已存在'))) {
                    alert('该邮箱已存在，请更换邮箱或直接登录。');
                } else if (typeof detail === 'string' && detail.includes('验证码')) {
                    alert(`注册失败：${detail}`);
                } else {
                    alert(`注册失败：${detail || response.status}`);
                }
            }
        } catch (error) {
            if (error && error.name === 'AbortError') {
                alert('注册请求超时（30秒）。请检查网络或稍后重试。');
            } else {
                console.error('Registration error:', error);
                alert('注册过程中出现错误。');
            }
        } finally {
            clearTimeout(timer);
            isRegistering = false;
            registerBtn.disabled = false;
        }
    }

    async function sendRegisterOtp() {
        const email = document.getElementById('register-email').value.trim();
        if (!email) { alert('请输入邮箱地址'); return; }
        try {
            sendRegisterOtpBtn.disabled = true;
            const resp = await fetch(`${apiBaseUrl}/api/v1/auth/otp/send/email`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: email })
            });
            if (resp.ok) { alert('验证码已发送，请查看您的邮箱'); } else {
                let msg = ''; try { msg = (await resp.json())?.detail || ''; } catch(_){}
                alert(`发送失败：${msg || resp.status}`);
            }
        } catch (e) { console.error('sendRegisterOtp error:', e); alert('发送验证码出现错误'); }
        finally { sendRegisterOtpBtn.disabled = false; }
    }

    async function sendPhoneOtp() {
        const phone_number = document.getElementById('otp-phone').value.trim();
        if (!phone_number) { alert('请输入手机号'); return; }
        try {
            sendOtpBtn.disabled = true;
            const resp = await fetch(`${apiBaseUrl}/api/v1/auth/otp/send`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone_number })
            });
            if (resp.ok) { alert('验证码已发送（开发环境：查看后端日志）'); } else {
                let msg = ''; try { msg = (await resp.json())?.detail || ''; } catch(_){}
                alert(`发送失败：${msg || resp.status}`);
            }
        } catch (e) { console.error('sendPhoneOtp error:', e); alert('发送验证码出现错误'); }
        finally { sendOtpBtn.disabled = false; }
    }

    async function sendEmailOtp() {
        const email = document.getElementById('email-otp-email').value.trim();
        if (!email) { alert('请输入邮箱地址'); return; }
        try {
            sendEmailOtpBtn.disabled = true;
            const resp = await fetch(`${apiBaseUrl}/api/v1/auth/otp/send/email`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: email, for_login: true })
            });
            if (resp.ok) { alert('验证码已发送，请查看您的邮箱'); } else {
                let msg = ''; try { msg = (await resp.json())?.detail || ''; } catch(_){}
                alert(`发送失败：${msg || resp.status}`);
            }
        } catch (e) { console.error('sendEmailOtp error:', e); alert('发送验证码出现错误'); }
        finally { sendEmailOtpBtn.disabled = false; }
    }

    async function loginByOtp() {
        if (isLoggingIn) { alert('正在登录，请稍候…'); return; }
        isLoggingIn = true;
        loginOtpBtn.disabled = true;
        const phone_number = document.getElementById('otp-phone').value.trim();
        const code = document.getElementById('otp-code').value.trim();
        try {
            const response = await fetch(`${apiBaseUrl}/api/v1/auth/login/otp`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone_number, code })
            });
            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('token', data.access_token);
                authContainer.style.display = 'none';
                mainContainer.style.display = 'flex';
                const languageToggle = document.querySelector('.language-toggle');
                if (languageToggle) languageToggle.style.display = 'none';
                updateLanguage(currentLang);
                currentQuerySessionId = null; currentOrganizeSessionId = null;
                if (chatWindow) { chatWindow.querySelectorAll('.chat-message').forEach(msg => msg.remove()); }
                fetchCurrentUser();
                return;
            }
            let errDetail = ''; try { errDetail = (await response.json())?.detail || ''; } catch(_){}
            alert(`登录失败：${errDetail || response.status}`);
        } catch (e) { console.error('loginByOtp error:', e); alert('登录过程中出现错误。'); }
        finally { isLoggingIn = false; loginOtpBtn.disabled = false; }
    }

    async function loginByEmailOtp() {
        if (isLoggingIn) { alert('正在登录，请稍候…'); return; }
        isLoggingIn = true;
        emailOtpLoginBtn.disabled = true;
        const email = document.getElementById('email-otp-email').value.trim();
        const code = document.getElementById('email-otp-code').value.trim();
        try {
            const response = await fetch(`${apiBaseUrl}/api/v1/auth/login/email-otp`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, code })
            });
            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('token', data.access_token);
                authContainer.style.display = 'none';
                mainContainer.style.display = 'flex';
                const languageToggle = document.querySelector('.language-toggle');
                if (languageToggle) languageToggle.style.display = 'none';
                updateLanguage(currentLang);
                currentQuerySessionId = null; currentOrganizeSessionId = null;
                if (chatWindow) { chatWindow.querySelectorAll('.chat-message').forEach(msg => msg.remove()); }
                fetchCurrentUser();
                return;
            }
            let errDetail = ''; try { errDetail = (await response.json())?.detail || ''; } catch(_){}
            alert(`登录失败：${errDetail || response.status}`);
        } catch (e) { console.error('loginByEmailOtp error:', e); alert('登录过程中出现错误。'); }
        finally { isLoggingIn = false; emailOtpLoginBtn.disabled = false; }
    }
    async function loginUser() {
        if (isLoggingIn) {
            alert('正在登录，请稍候…');
            return;
        }
        isLoggingIn = true;
        loginBtn.disabled = true;

        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;

        const payload = { username, password };

        try {
            console.log('Login: sending request', { username, url: `${apiBaseUrl}/api/v1/auth/login` });
            const response = await fetch(`${apiBaseUrl}/api/v1/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            console.log('Login: response status', response.status);

            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('token', data.access_token);
                authContainer.style.display = 'none';
                mainContainer.style.display = 'flex';
                const languageToggle = document.querySelector('.language-toggle');
                if (languageToggle) languageToggle.style.display = 'none';
                updateLanguage(currentLang);
                // 登录后清空所有sessionId，进入新会话
                currentQuerySessionId = null;
                currentOrganizeSessionId = null;
                // 清空聊天窗口
                if (chatWindow) {
                    const messages = chatWindow.querySelectorAll('.chat-message');
                    messages.forEach(msg => msg.remove());
                }
                fetchCurrentUser();
                // 登录后不再加载任何历史，等待用户点击历史按钮
                return;
            }

            // 登录失败时，尝试读取错误信息
            let errDetail = '';
            try {
                const errJson = await response.json();
                errDetail = errJson?.detail || '';
            } catch (_) {}

            // 仅提示引导注册，不做自动注册
            if (response.status === 401 && (errDetail.includes('用户名或密码错误') || errDetail.includes('用户名/手机号或密码错误') || errDetail.includes('Unauthorized'))) {
                alert('用户名/手机号或密码错误。如果尚未注册，请前往注册页面完成注册。');
                // 引导到注册页并预填信息
                document.getElementById('register-username').value = username;
                document.getElementById('register-email').value = `${username}@example.com`;
                document.getElementById('register-password').value = password;
                loginForm.style.display = 'none';
                registerForm.style.display = 'block';
                return;
            }

            // 其他登录失败情况
            alert(`登录失败：${errDetail || response.status}`);
        } catch (error) {
            console.error('Login error:', error);
            alert('登录过程中出现错误。');
        } finally {
            isLoggingIn = false;
            loginBtn.disabled = false;
        }
    }

    // --- Documents: create text document API ---
    async function createTextDocument({ title, content, tags = [], metadata = {} }) {
        const token = localStorage.getItem('token');
        if (!token) {
            alert('请先登录');
            return null;
        }
        try {
            const resp = await fetch(`${apiBaseUrl}/api/v1/documents/create`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ title, content, file_type: 'text', tags, metadata })
            });
            if (!resp.ok) {
                let msg = '';
                try { msg = (await resp.json())?.detail || ''; } catch (_) {}
                alert(`创建文档失败：${msg || resp.status}`);
                return null;
            }
            const doc = await resp.json();
            await fetchDocuments();
            return doc;
        } catch (e) {
            console.error('Create text doc error:', e);
            alert('创建文档时出现错误。');
            return null;
        }
    }

    function logoutUser() {
        // 单用户模式：退出后刷新页面即可重新进入主界面
        try { closeActiveSessions(); } catch (_) {}
        window.location.reload();
    }

    async function fetchCurrentUser() {
        // 单用户模式：直接设置默认用户信息，不调用认证 API
        const defaultUser = { username: 'Admin', avatar_url: null };

        // 显示用户首字母头像
        if (userAvatar) {
            const initials = defaultUser.username.charAt(0).toUpperCase();
            userAvatar.innerHTML = `<span id="avatar-text">${initials}</span>`;
        }
        if (dropdownUsername) dropdownUsername.textContent = defaultUser.username;
        // 强制初始化布局样式
        const docMgmt = document.getElementById('document-management');
        if (docMgmt) docMgmt.style.display = 'flex';
        // 加载文档列表
        fetchDocuments();
    }

    // 用户头像下拉与统计弹窗事件（鼠标悬停显示）
    const userAvatarContainer = document.querySelector('.user-avatar-container');
    let hideDropdownTimer = null;
    
    // 鼠标移入头像容器时显示下拉菜单（包括头像和下拉菜单区域）
    userAvatarContainer?.addEventListener('mouseenter', () => {
        // 取消任何延迟隐藏
        if (hideDropdownTimer) {
            clearTimeout(hideDropdownTimer);
            hideDropdownTimer = null;
        }
        if (userDropdown) userDropdown.style.display = 'block';
    });
    
    // 鼠标移出整个容器时延迟隐藏下拉菜单（防止鼠标快速移动时意外关闭）
    userAvatarContainer?.addEventListener('mouseleave', () => {
        hideDropdownTimer = setTimeout(() => {
            if (userDropdown) userDropdown.style.display = 'none';
        }, 100); // 100ms延迟
    });
    
    menuLogout?.addEventListener('click', (e) => { e.preventDefault(); userDropdown.style.display = 'none'; logoutUser(); });
    
    // 个人信息编辑功能
    const profileModal = document.getElementById('profile-modal');
    const profileModalClose = document.getElementById('profile-modal-close');
    const profileForm = document.getElementById('profile-form');
    const profileUsername = document.getElementById('profile-username');
    const profileEmail = document.getElementById('profile-email');
    const profilePhone = document.getElementById('profile-phone');
    const profileCancelBtn = document.getElementById('profile-cancel-btn');
    const profileSaveBtn = document.getElementById('profile-save-btn');
    const menuProfile = document.getElementById('menu-profile');
    const changeEmailBtn = document.getElementById('change-email-btn');
    const changeEmailModal = document.getElementById('change-email-modal');
    const changeEmailModalClose = document.getElementById('change-email-modal-close');
    const changeEmailForm = document.getElementById('change-email-form');
    const oldEmailDisplay = document.getElementById('old-email-display');
    const newEmail = document.getElementById('new-email');
    const newEmailOtp = document.getElementById('new-email-otp');
    const sendNewEmailOtpBtn = document.getElementById('send-new-email-otp-btn');
    const changeEmailCancelBtn = document.getElementById('change-email-cancel-btn');
    const changeEmailSaveBtn = document.getElementById('change-email-save-btn');
    
    // 修改密码相关元素
    const changePasswordBtn = document.getElementById('change-password-btn');
    const changePasswordModal = document.getElementById('change-password-modal');
    const changePasswordModalClose = document.getElementById('change-password-modal-close');
    const changePasswordForm = document.getElementById('change-password-form');
    const oldPassword = document.getElementById('old-password');
    const newPassword = document.getElementById('new-password');
    const newPasswordConfirm = document.getElementById('new-password-confirm');
    const changePasswordCancelBtn = document.getElementById('change-password-cancel-btn');
    const changePasswordSaveBtn = document.getElementById('change-password-save-btn');
    
    // 点击菜单项打开资料编辑弹窗
    menuProfile?.addEventListener('click', async (e) => {
        e.preventDefault();
        if (userDropdown) userDropdown.style.display = 'none';
        
        // 获取当前用户信息并填充表单
        const token = localStorage.getItem('token');
        if (!token) {
            alert('请先登录');
            return;
        }
        
        try {
            const response = await fetch(`${apiBaseUrl}/api/v1/auth/me`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (response.ok) {
                const user = await response.json();
                if (profileUsername) profileUsername.value = user.username || '';
                if (profileEmail) profileEmail.value = user.email || '';
                if (profilePhone) profilePhone.value = user.phone_number || '';
                
                if (profileModal) profileModal.style.display = 'flex';
            } else {
                alert('获取用户信息失败');
            }
        } catch (error) {
            console.error('Failed to fetch user info:', error);
            alert('网络错误');
        }
    });
    
    // 点击修改密码按钮
    changePasswordBtn?.addEventListener('click', () => {
        if (changePasswordModal) changePasswordModal.style.display = 'flex';
        
        // 清空表单
        if (oldPassword) oldPassword.value = '';
        if (newPassword) newPassword.value = '';
        if (newPasswordConfirm) newPasswordConfirm.value = '';
    });
    
    // 关闭修改密码弹窗
    changePasswordModalClose?.addEventListener('click', () => {
        if (changePasswordModal) changePasswordModal.style.display = 'none';
    });
    
    changePasswordCancelBtn?.addEventListener('click', () => {
        if (changePasswordModal) changePasswordModal.style.display = 'none';
    });
    
    // 点击遮罩层关闭修改密码弹窗
    changePasswordModal?.addEventListener('click', (e) => {
        if (e.target === changePasswordModal) {
            changePasswordModal.style.display = 'none';
        }
    });
    
    // 提交修改密码表单
    changePasswordForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const token = localStorage.getItem('token');
        if (!token) {
            alert('请先登录');
            return;
        }
        
        const oldPass = oldPassword?.value.trim();
        const newPass = newPassword?.value.trim();
        const confirmPass = newPasswordConfirm?.value.trim();
        
        if (!oldPass || !newPass || !confirmPass) {
            alert('请填写所有密码字段');
            return;
        }
        
        if (newPass !== confirmPass) {
            alert('两次输入的新密码不一致');
            return;
        }
        
        if (newPass.length < 6) {
            alert('密码长度至少6位');
            return;
        }
        
        if (oldPass === newPass) {
            alert('新密码不能与旧密码相同');
            return;
        }
        
        try {
            if (changePasswordSaveBtn) {
                changePasswordSaveBtn.disabled = true;
                changePasswordSaveBtn.textContent = '保存中...';
            }
            
            const updateData = {
                old_password: oldPass,
                new_password: newPass
            };
            
            const response = await fetch(`${apiBaseUrl}/api/v1/users/profile/password`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updateData)
            });
            
            if (response.ok) {
                alert('密码修改成功！请使用新密码重新登录');
                if (changePasswordModal) changePasswordModal.style.display = 'none';
                
                // 清除token，跳转到登录页
                localStorage.removeItem('token');
                location.reload();
            } else {
                let msg = '';
                try { msg = (await response.json())?.detail || ''; } catch (_) {}
                alert(`修改失败：${msg || response.status}`);
            }
        } catch (error) {
            console.error('Password update error:', error);
            alert('修改密码时出现错误');
        } finally {
            if (changePasswordSaveBtn) {
                changePasswordSaveBtn.disabled = false;
                changePasswordSaveBtn.textContent = '确认修改';
            }
        }
    });
    
    // 点击修改邮箱按钮
    changeEmailBtn?.addEventListener('click', () => {
        if (changeEmailModal) changeEmailModal.style.display = 'flex';
        
        if (oldEmailDisplay && profileEmail) {
            oldEmailDisplay.textContent = profileEmail.value;
        }
        
        if (newEmail) newEmail.value = '';
        if (newEmailOtp) newEmailOtp.value = '';
    });
    
    // 关闭修改邮箱弹窗
    changeEmailModalClose?.addEventListener('click', () => {
        if (changeEmailModal) changeEmailModal.style.display = 'none';
    });
    
    changeEmailCancelBtn?.addEventListener('click', () => {
        if (changeEmailModal) changeEmailModal.style.display = 'none';
    });
    
    // 点击遮罩层关闭修改邮箱弹窗
    changeEmailModal?.addEventListener('click', (e) => {
        if (e.target === changeEmailModal) {
            changeEmailModal.style.display = 'none';
        }
    });
    
    // 关闭弹窗
    profileModalClose?.addEventListener('click', () => {
        if (profileModal) profileModal.style.display = 'none';
    });
    
    profileCancelBtn?.addEventListener('click', () => {
        if (profileModal) profileModal.style.display = 'none';
    });
    
    // 发送新邮箱验证码
    sendNewEmailOtpBtn?.addEventListener('click', async () => {
        const email = newEmail?.value.trim();
        if (!email) { alert('请输入新邮箱地址'); return; }
        try {
            sendNewEmailOtpBtn.disabled = true;
            const resp = await fetch(`${apiBaseUrl}/api/v1/auth/otp/send/email`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: email })
            });
            if (resp.ok) { alert('验证码已发送，请查看您的邮箱'); } else {
                let msg = ''; try { msg = (await resp.json())?.detail || ''; } catch(_){}
                alert(`发送失败：${msg || resp.status}`);
            }
        } catch (e) { console.error('sendNewEmailOtp error:', e); alert('发送验证码出现错误'); }
        finally { sendNewEmailOtpBtn.disabled = false; }
    });
    
    // 提交表单
    profileForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const token = localStorage.getItem('token');
        if (!token) {
            alert('请先登录');
            return;
        }
        
        const username = profileUsername?.value.trim();
        const phone = profilePhone?.value.trim();
        
        if (!username || username.length < 3) {
            alert('用户名至少需要3个字符');
            return;
        }
        
        try {
            if (profileSaveBtn) {
                profileSaveBtn.disabled = true;
                profileSaveBtn.textContent = '保存中...';
            }
            
            const updateData = {
                username,
                phone_number: phone || null
            };
            
            const response = await fetch(`${apiBaseUrl}/api/v1/users/profile`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updateData)
            });
            
            if (response.ok) {
                alert('资料保存成功！');
                if (profileModal) profileModal.style.display = 'none';
                
                // 重新加载用户信息
                await fetchCurrentUser();
            } else {
                let msg = '';
                try { msg = (await response.json())?.detail || ''; } catch (_) {}
                alert(`保存失败：${msg || response.status}`);
            }
        } catch (error) {
            console.error('Profile update error:', error);
            alert('保存时出现错误');
        } finally {
            if (profileSaveBtn) {
                profileSaveBtn.disabled = false;
                profileSaveBtn.textContent = '保存';
            }
        }
    });
    
    // 提交修改邮箱表单
    changeEmailForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const token = localStorage.getItem('token');
        if (!token) {
            alert('请先登录');
            return;
        }
        
        const oldEmailValue = profileEmail?.value.trim();
        const newEmailValue = newEmail?.value.trim();
        const newOtp = newEmailOtp?.value.trim();
        
        if (!newEmailValue || !newOtp) {
            alert('请输入新邮箱和验证码');
            return;
        }
        
        if (newEmailValue === oldEmailValue) {
            alert('新邮箱与当前邮箱相同，无需修改');
            return;
        }
        
        try {
            if (changeEmailSaveBtn) {
                changeEmailSaveBtn.disabled = true;
                changeEmailSaveBtn.textContent = '保存中...';
            }
            
            const updateData = {
                email: newEmailValue,
                new_email_otp: newOtp
            };
            
            const response = await fetch(`${apiBaseUrl}/api/v1/users/profile/email`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updateData)
            });
            
            if (response.ok) {
                alert('邮箱修改成功！');
                if (changeEmailModal) changeEmailModal.style.display = 'none';
                
                if (profileEmail) profileEmail.value = newEmailValue;
                
                await fetchCurrentUser();
            } else {
                let msg = '';
                try { msg = (await response.json())?.detail || ''; } catch (_) {}
                alert(`保存失败：${msg || response.status}`);
            }
        } catch (error) {
            console.error('Email update error:', error);
            alert('保存时出现错误');
        } finally {
            if (changeEmailSaveBtn) {
                changeEmailSaveBtn.disabled = false;
                changeEmailSaveBtn.textContent = '确认修改';
            }
        }
    });
    
    // 头像上传功能
    const avatarModal = document.getElementById('avatar-modal');
    const avatarModalClose = document.getElementById('avatar-modal-close');
    const avatarPreview = document.getElementById('avatar-preview');
    const avatarPreviewImg = document.getElementById('avatar-preview-img');
    const avatarPreviewText = document.getElementById('avatar-preview-text');
    const avatarFileInput = document.getElementById('avatar-file-input');
    const avatarUploadBtn = document.getElementById('avatar-upload-btn');
    const menuUploadAvatar = document.getElementById('menu-upload-avatar');
    
    let selectedAvatarFile = null;
    
    menuUploadAvatar?.addEventListener('click', (e) => {
        e.preventDefault();
        if (avatarModal) avatarModal.style.display = 'flex';
        if (userDropdown) userDropdown.style.display = 'none';
        // 重置状态
        selectedAvatarFile = null;
        if (avatarPreviewImg) avatarPreviewImg.style.display = 'none';
        if (avatarPreviewText) avatarPreviewText.style.display = 'block';
        if (avatarUploadBtn) avatarUploadBtn.disabled = true;
    });
    
    avatarModalClose?.addEventListener('click', () => {
        if (avatarModal) avatarModal.style.display = 'none';
    });
    
    // 点击遮罩层关闭弹窗
    avatarModal?.addEventListener('click', (e) => {
        if (e.target === avatarModal) {
            avatarModal.style.display = 'none';
        }
    });
    
    avatarPreview?.addEventListener('click', () => {
        avatarFileInput?.click();
    });
    
    avatarFileInput?.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        // 验证文件类型
        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
        if (!allowedTypes.includes(file.type)) {
            alert('不支持的文件类型，请上传 JPEG、PNG、GIF 或 WebP 格式的图片');
            e.target.value = '';
            return;
        }
        
        // 验证文件大小
        if (file.size > 5 * 1024 * 1024) {
            alert('头像文件大小不能超过 5MB');
            e.target.value = '';
            return;
        }
        
        // 预览图片
        const reader = new FileReader();
        reader.onload = (ev) => {
            if (avatarPreviewImg) {
                avatarPreviewImg.src = ev.target.result;
                avatarPreviewImg.style.display = 'block';
            }
            if (avatarPreviewText) avatarPreviewText.style.display = 'none';
        };
        reader.readAsDataURL(file);
        
        selectedAvatarFile = file;
        if (avatarUploadBtn) avatarUploadBtn.disabled = false;
    });
    
    avatarUploadBtn?.addEventListener('click', async () => {
        if (!selectedAvatarFile) return;
        
        const token = localStorage.getItem('token');
        if (!token) {
            alert('请先登录');
            return;
        }
        
        try {
            avatarUploadBtn.disabled = true;
            avatarUploadBtn.textContent = '上传中...';
            
            const formData = new FormData();
            formData.append('file', selectedAvatarFile);
            
            const response = await fetch(`${apiBaseUrl}/api/v1/users/avatar`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            });
            
            if (response.ok) {
                const user = await response.json();
                console.log('🎯 Avatar upload success!');
                
                alert('头像上传成功！');
                
                // 关闭弹窗
                if (avatarModal) avatarModal.style.display = 'none';
                
                // 重新加载用户信息以刷新头像
                console.log('🔄 Reloading user info to refresh avatar...');
                await fetchCurrentUser();
                console.log('✅ User info reloaded!');
            } else {
                let msg = '';
                try { msg = (await response.json())?.detail || ''; } catch (_) {}
                alert(`上传失败：${msg || response.status}`);
            }
        } catch (error) {
            console.error('Avatar upload error:', error);
            alert('上传头像时出现错误');
        } finally {
            if (avatarUploadBtn) {
                avatarUploadBtn.disabled = false;
                avatarUploadBtn.textContent = '上传';
            }
        }
    });
    
    // 语言切换菜单项
    const menuLanguage = document.getElementById('menu-language');
    menuLanguage?.addEventListener('click', (e) => {
        e.preventDefault();
        const newLang = currentLang === 'zh' ? 'en' : 'zh';
        updateLanguage(newLang);
        if (userDropdown) userDropdown.style.display = 'none';
    });
    // 直接选择具体语言
    const menuLangZh = document.getElementById('menu-lang-zh');
    const menuLangEn = document.getElementById('menu-lang-en');
    menuLangZh?.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); updateLanguage('zh'); if (userDropdown) userDropdown.style.display = 'none'; });
    menuLangEn?.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); updateLanguage('en'); if (userDropdown) userDropdown.style.display = 'none'; });

    // 使用统计弹窗
    const statsModal = document.getElementById('stats-modal');
    const statsModalClose = document.getElementById('stats-modal-close');
    const statsMonthPicker = document.getElementById('stats-month-picker');
    const statsGrid = document.getElementById('stats-grid');
    const statsTooltip = document.getElementById('stats-tooltip');

    menuStatistics?.addEventListener('click', (e) => {
        e.preventDefault();
        if (!statsModal) return;
        statsModal.style.display = 'flex';  // 使用flex实现居中
        const now = new Date();
        const ym = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
        if (statsMonthPicker) statsMonthPicker.value = ym;
        buildStatsGrid(ym);
    });
    statsModalClose?.addEventListener('click', () => { if (statsModal) statsModal.style.display = 'none'; });
    statsMonthPicker?.addEventListener('change', (e) => { buildStatsGrid(e.target.value); });

    function levelForCounts(c){
        const t = c.queries + c.added + c.deleted;
        if (t === 0) return 0; 
        if (t <= 2) return 1; 
        if (t <= 5) return 2; 
        if (t <= 9) return 3; 
        return 4;
    }
    
    function positionTooltip(ev, html){
        if (!statsTooltip) return;
        statsTooltip.innerHTML = html;
        const tooltipRect = statsTooltip.getBoundingClientRect();
        let left = ev.clientX + 12;
        let top = ev.clientY - tooltipRect.height - 12;
        
        // 防止tooltip超出视口
        if (left + tooltipRect.width > window.innerWidth) {
            left = ev.clientX - tooltipRect.width - 12;
        }
        if (top < 0) {
            top = ev.clientY + 12;
        }
        
        statsTooltip.style.left = left + 'px';
        statsTooltip.style.top = top + 'px';
        statsTooltip.style.display = 'block';
    }
    function hideTooltip(){ if (statsTooltip) statsTooltip.style.display = 'none'; }

    async function buildStatsGrid(ym){
        if (!statsGrid) return;
        statsGrid.innerHTML = '';
        const [year, month] = ym.split('-').map(n=>parseInt(n,10));
        const first = new Date(year, month-1, 1);
        const days = new Date(year, month, 0).getDate();
        
        // 先填充第一周前导占位
        for(let i=0;i<first.getDay();i++){
            const cell = document.createElement('div'); 
            cell.className='stats-cell level-0 empty'; 
            statsGrid.appendChild(cell);
        }
        
        const stats = await loadUsageStats(ym);
        
        // 计算总计
        let totalQueries = 0;
        let totalAdded = 0;
        let totalDeleted = 0;
        let activeDays = 0;
        
        for(let d=1; d<=days; d++){
            const date = new Date(year, month-1, d);
            const key = `${year}-${String(month).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
            const c = stats[key] || { queries:0, added:0, deleted:0 };
            const lvl = levelForCounts(c);
            
            // 累加总计
            totalQueries += c.queries;
            totalAdded += c.added;
            totalDeleted += c.deleted;
            if (lvl > 0) activeDays++;
            
            const cell = document.createElement('div');
            cell.className = `stats-cell level-${lvl}`;
            cell.title = key;
            
            // 构建详细tooltip
            const tooltipHtml = `
                <div style="font-weight: 600; margin-bottom: 4px;">${key}</div>
                <div>🔍 查询：<strong>${c.queries}</strong> 次</div>
                <div>➕ 新增：<strong>${c.added}</strong> 个</div>
                <div>🗑️ 删除：<strong>${c.deleted}</strong> 个</div>
                <div style="margin-top: 4px; padding-top: 4px; border-top: 1px solid rgba(255,255,255,0.2);">
                    总计：<strong>${c.queries + c.added + c.deleted}</strong> 次操作
                </div>
            `;
            
            cell.addEventListener('mouseenter', (ev)=> positionTooltip(ev, tooltipHtml));
            cell.addEventListener('mouseleave', hideTooltip);
            statsGrid.appendChild(cell);
        }
        
        // 更新统计概览
        const totalQueriesEl = document.getElementById('stats-total-queries');
        const totalAddedEl = document.getElementById('stats-total-added');
        const totalDeletedEl = document.getElementById('stats-total-deleted');
        const activeDaysEl = document.getElementById('stats-active-days');
        
        if (totalQueriesEl) totalQueriesEl.textContent = totalQueries;
        if (totalAddedEl) totalAddedEl.textContent = totalAdded;
        if (totalDeletedEl) totalDeletedEl.textContent = totalDeleted;
        if (activeDaysEl) activeDaysEl.textContent = activeDays;
    }
    async function loadUsageStats(ym){
        const token = localStorage.getItem('token');
        if (!token) return {};
        try{
            const resp = await fetch(`${apiBaseUrl}/api/v1/stats/usage?month=${ym}`, { headers: { 'Authorization': `Bearer ${token}` }});
            if (!resp.ok) return {};
            return await resp.json();
        }catch(e){ console.warn('loadUsageStats', e); return {}; }
    }

    async function fetchDocuments() {
        const token = localStorage.getItem('token');
        if (!token) {
            console.warn('No token found, cannot fetch documents');
            return;
        }

        try {
            console.log('Fetching documents from:', `${apiBaseUrl}/api/v1/documents/`);
            const response = await fetch(`${apiBaseUrl}/api/v1/documents/`,
             {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            console.log('Response status:', response.status);
            if (response.ok) {
                const data = await response.json();
                console.log('Received data:', data);
                // 适配新的响应格式：{ documents: [...], total: n, skip: n, limit: n }
                const documents = data.documents || data;
                console.log('Documents to render:', documents?.length ?? 0);
                renderDocuments(documents);
            } else {
                console.error('Failed to fetch documents, status:', response.status);
                const errorText = await response.text();
                console.error('Error response:', errorText);
            }
        } catch (error) {
            console.error('Error fetching documents:', error);
        }
    }

    async function fetchDeletedDocuments() {
        const token = localStorage.getItem('token');
        if (!token) {
            alert('请先登录后再打开回收站');
            return;
        }
        try {
            const response = await fetch(`${apiBaseUrl}/api/v1/documents/deleted`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            console.log('fetchDeletedDocuments status:', response.status);
            if (response.ok) {
                const docs = await response.json();
                renderDeletedDocuments(docs);
            } else {
                let msg = '';
                try { msg = (await response.json())?.detail || ''; } catch (_) {}
                alert(`无法加载回收站：${msg || response.status}`);
            }
        } catch (error) {
            console.error('Error fetching deleted documents:', error);
            alert('打开回收站失败，网络或服务器异常。');
        }
    }

    // 恢复缺失的上传函数
    async function uploadDocument() {
        const token = localStorage.getItem('token');
        if (!token) {
            alert('请先登录');
            return;
        }
        const file = fileInput.files[0];
        const title = documentTitle.value.trim();
        if (!file || !title) {
            alert('请选择文件并填写标题');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('title', title);
        // 可选字段：tags/metadata，当前界面未提供输入，故不附加

        try {
            uploadBtn.disabled = true;
            const resp = await fetch(`${apiBaseUrl}/api/v1/documents/upload`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });
            if (resp.ok) {
                fileInput.value = '';
                documentTitle.value = '';
                await fetchDocuments();
                alert('上传成功');
            } else {
                let msg = '';
                try { msg = (await resp.json())?.detail || ''; } catch (_) {}
                alert(`上传失败：${msg || resp.status}`);
            }
        } catch (e) {
            console.error('Upload error:', e);
            alert('上传过程中出现错误。');
        } finally {
            uploadBtn.disabled = false;
        }
    }

    // --- Source Modal Logic ---
    function openSourceModal() {
        if (sourceModal) sourceModal.style.display = 'flex';
    }
    function closeSourceModal() {
        if (sourceModal) sourceModal.style.display = 'none';
    }
    function setActiveSourceTab(tab) {
        if (!tabUrlBtn || !tabFileBtn) return;
        const isUrl = tab === 'url';
        tabUrlBtn.classList.toggle('active', isUrl);
        tabFileBtn.classList.toggle('active', !isUrl);
        if (tabUrlBody) tabUrlBody.style.display = isUrl ? 'block' : 'none';
        if (tabFileBody) tabFileBody.style.display = isUrl ? 'none' : 'block';
    }

    async function submitUrlSource() {
        const url = (sourceUrlInput?.value || '').trim();
        const title = (sourceUrlTitle?.value || '').trim() || '网页来源';
        if (!url) { alert('请输入网址'); return; }
        const token = localStorage.getItem('token');
        if (!token) { alert('请先登录'); return; }

        // 开始进度条
        let progress = 0;
        let progTimer = null;
        const showProgress = () => {
            if (urlCrawlProgress) urlCrawlProgress.style.display = 'block';
            if (urlCrawlProgressBar) urlCrawlProgressBar.style.width = `${progress}%`;
            if (urlCrawlProgressLabel) urlCrawlProgressLabel.textContent = `抓取中… ${Math.floor(progress)}%`;
        };
        const startProgress = () => {
            progress = 0;
            showProgress();
            progTimer = setInterval(() => {
                const step = Math.random() * 10 + 5; // 5-15%
                progress = Math.min(progress + step, 90);
                showProgress();
            }, 300);
        };
        const finishProgress = (ok = true) => {
            if (progTimer) { clearInterval(progTimer); progTimer = null; }
            progress = 100;
            if (urlCrawlProgressBar) urlCrawlProgressBar.style.width = '100%';
            if (urlCrawlProgressLabel) urlCrawlProgressLabel.textContent = ok ? '抓取完成' : '抓取失败';
            setTimeout(() => { if (urlCrawlProgress) urlCrawlProgress.style.display = 'none'; }, 800);
        };

        // 调用后端抓取API，返回markdown/text，仅用于整理，不入库
        try {
            submitUrlBtn.disabled = true;
            if (sourceUrlInput) sourceUrlInput.disabled = true;
            if (sourceUrlTitle) sourceUrlTitle.disabled = true;
            startProgress();
            const resp = await fetch(`${apiBaseUrl}/api/v1/scrape/url`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    url,
                    title
                })
            });
            if (!resp.ok) {
                let msg = '';
                try {
                    const body = await resp.json();
                    const d = body?.detail;
                    if (typeof d === 'string') {
                        msg = d;
                    } else if (d && typeof d === 'object') {
                        msg = d.error || d.message || JSON.stringify(d);
                    }
                } catch (_) {}
                finishProgress(false);
                const statusText = resp.statusText || '';
                alert(`抓取失败：${msg || `${resp.status} ${statusText}`}`);
                return;
            }
            const data = await resp.json();
            const content = (data.markdown || '').trim();
            if (!content) {
                finishProgress(false);
                alert('抓取成功但未返回内容');
                return;
            }
            finishProgress(true);
            // 记录来源元数据，供后续“保存为知识文件”使用
            currentSourceMeta = { url, title };
            // 进入知识梳理模式，填充并发送
            if (!isOrganizeMode) setMode(true);
            const maxLen = 8000; // 避免输入过长
            const sliced = content.length > maxLen ? `${content.slice(0, maxLen)}\n\n（内容较长，已截断）` : content;
            if (chatMessage) {
                chatMessage.value = `请对以下网页进行知识梳理并总结，涵盖结构、关键要点、结论与建议：\n\n${sliced}`;
                sendChatBtn.click();
            }
            closeSourceModal();
            if (sourceUrlInput) sourceUrlInput.value = '';
            if (sourceUrlTitle) sourceUrlTitle.value = '';
        } catch (e) {
            console.error('Submit URL source error:', e);
            finishProgress(false);
            alert('提交网址时出现错误。');
        } finally {
            submitUrlBtn.disabled = false;
            if (sourceUrlInput) sourceUrlInput.disabled = false;
            if (sourceUrlTitle) sourceUrlTitle.disabled = false;
        }
    }

    async function submitFileSource() {
        const file = sourceFileInput?.files?.[0];
        const title = (sourceFileTitle?.value || '').trim();
        if (!file || !title) { alert('请选择文件并填写标题'); return; }

        const token = localStorage.getItem('token');
        if (!token) { alert('请先登录'); return; }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('title', title);

        try {
            submitFileBtn.disabled = true;
            const resp = await fetch(`${apiBaseUrl}/api/v1/documents/upload`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });
            if (!resp.ok) {
                let msg = '';
                try { msg = (await resp.json())?.detail || ''; } catch (_) {}
                alert(`上传失败：${msg || resp.status}`);
                return;
            }
            await fetchDocuments();
            alert('上传成功并已保存到知识库');
            closeSourceModal();
            if (sourceFileInput) sourceFileInput.value = '';
            if (sourceFileTitle) sourceFileTitle.value = '';
        } catch (e) {
            console.error('Upload source error:', e);
            alert('上传过程中出现错误。');
        } finally {
            submitFileBtn.disabled = false;
        }
    }

    // 恢复缺失的查看文档内容函数
    async function fetchDocumentContent(docId) {
        console.log('fetchDocumentContent called, docId:', docId);
        const token = localStorage.getItem('token');
        if (!token) {
            console.error('No token found');
            return;
        }
        try {
            const resp = await fetch(`${apiBaseUrl}/api/v1/documents/${docId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            console.log('Document fetch response status:', resp.status);
            if (resp.ok) {
                const doc = await resp.json();
                console.log('Document fetched:', doc.title);
                
                if (!documentViewer || !docViewTitle || !docViewContent) {
                    console.error('Document viewer elements not found:', {
                        documentViewer: !!documentViewer,
                        docViewTitle: !!docViewTitle,
                        docViewContent: !!docViewContent
                    });
                    return;
                }
                
                docViewTitle.textContent = doc.title;
                // 显示完整的文档内容，不再截断
                const fullText = (doc.content || '该文档暂无内容或正在处理。');
                docViewContent.textContent = fullText;
                // 在左栏内部显示预览，与列表互斥
                documentViewer.style.display = 'block';
                console.log('Document viewer displayed');
                // 不再隐藏uploadForm，让CSS完全控制（uploadForm应该固定在底部）
                // uploadForm.style.display = 'none';  // 移除这行，避免影响布局
            } else {
                let msg = '';
                try { msg = (await resp.json())?.detail || ''; } catch (_) {}
                console.error('Failed to fetch document:', msg || resp.status);
                alert(`获取文档失败：${msg || resp.status}`);
            }
        } catch (e) {
            console.error('Fetch doc error:', e);
            alert('获取文档内容出现错误。');
        }
    }

    function renderDocuments(documents) {
        console.log('Render documents count:', documents?.length ?? 0);
        
        if (!documentList) {
            console.error('documentList element not found!');
            return;
        }
        
        documentList.innerHTML = '';
        if (!Array.isArray(documents) || documents.length === 0) {
            documentList.innerHTML = '<p style="color: var(--text-tertiary); padding: 20px; text-align: center;">暂无文档，请上传文件</p>';
            console.log('No documents to display');
            return;
        }

        documents.forEach((doc, index) => {
            const docElement = document.createElement('div');
            docElement.classList.add('document-item');
            docElement.dataset.docId = doc.document_id;

            const titleSpan = document.createElement('span');
            titleSpan.textContent = doc.title;
            titleSpan.classList.add('document-title');

            const deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.textContent = '';  // 使用CSS::before添加图标
            deleteBtn.classList.add('delete-icon');
            deleteBtn.title = '移入回收站';
            deleteBtn.dataset.docId = doc.document_id;
            // 防止按钮挤压标题
            deleteBtn.style.minWidth = '40px';

            docElement.appendChild(titleSpan);
            docElement.appendChild(deleteBtn);
            documentList.appendChild(docElement);
            
            console.log(`Rendered document ${index + 1}:`, doc.title);
        });
        
        console.log('Total documents rendered:', documents.length);
    }

    function renderDeletedDocuments(documents) {
        deletedDocumentList.innerHTML = '';
        if (documents.length === 0) {
            deletedDocumentList.innerHTML = '<p>回收站为空。</p>';
            return;
        }
        documents.forEach(doc => {
            const item = document.createElement('div');
            item.classList.add('deleted-document-item');
            item.dataset.docId = doc.document_id;

            const titleSpan = document.createElement('span');
            titleSpan.textContent = doc.title;
            titleSpan.classList.add('document-title');

            const actions = document.createElement('div');
            actions.classList.add('deleted-actions');

            const restoreBtn = document.createElement('button');
            restoreBtn.textContent = '恢复';
            restoreBtn.classList.add('restore-btn');
            restoreBtn.dataset.docId = doc.document_id;

            const purgeBtn = document.createElement('button');
            purgeBtn.textContent = '彻底删除';
            purgeBtn.classList.add('purge-btn');
            purgeBtn.dataset.docId = doc.document_id;

            actions.appendChild(restoreBtn);
            actions.appendChild(purgeBtn);

            item.appendChild(titleSpan);
            item.appendChild(actions);
            deletedDocumentList.appendChild(item);
        });
    }

    async function deleteDocumentById(docId) {
        const token = localStorage.getItem('token');
        if (!token) return;
        if (!confirm('确认将该文档移入回收站吗？')) return;
        try {
            const resp = await fetch(`${apiBaseUrl}/api/v1/documents/${docId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (resp.ok) {
                await fetchDocuments();
                await fetchDeletedDocuments();
            } else {
                let msg = '';
                try { msg = (await resp.json())?.detail || ''; } catch (_) {}
                alert(`删除失败：${msg || resp.status}`);
            }
        } catch (e) {
            console.error('Delete error:', e);
            alert('删除过程中出现错误。');
        }
    }

    async function restoreDocumentById(docId) {
        const token = localStorage.getItem('token');
        if (!token) return;
        try {
            const resp = await fetch(`${apiBaseUrl}/api/v1/documents/${docId}/restore`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (resp.ok) {
                await fetchDocuments();
                await fetchDeletedDocuments();
            } else {
                let msg = '';
                try { msg = (await resp.json())?.detail || ''; } catch (_) {}
                alert(`恢复失败：${msg || resp.status}`);
            }
        } catch (e) {
            console.error('Restore error:', e);
            alert('恢复过程中出现错误。');
        }
    }

    async function purgeDocumentById(docId) {
        const token = localStorage.getItem('token');
        if (!token) return;
        if (!confirm('确认彻底删除该文档吗？该操作不可恢复。')) return;
        try {
            const resp = await fetch(`${apiBaseUrl}/api/v1/documents/${docId}/purge`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (resp.ok) {
                await fetchDeletedDocuments();
            } else {
                let msg = '';
                try { msg = (await resp.json())?.detail || ''; } catch (_) {}
                alert(`彻底删除失败：${msg || resp.status}`);
            }
        } catch (e) {
            console.error('Purge error:', e);
            alert('彻底删除过程中出现错误。');
        }
    }

    function showDocumentList() {
        document.getElementById('document-management').style.display = 'flex';  // 使用flex保持flexbox布局
        documentViewer.style.display = 'none';
        // 不再设置documentList.style.display，让CSS完全控制
        // 不再设置uploadForm.style.display，让CSS完全控制
        trashManagement.style.display = 'none';
    }

    function showTrashList() {
        console.log('UI: showTrashList called');
        document.getElementById('document-management').style.display = 'none';
        documentViewer.style.display = 'none';
        trashManagement.style.display = 'flex';  // 使用flex保持flexbox布局
    }

    async function sendChatMessage() {
        const message = chatMessage.value.trim();
        if (!message) return;

        appendMessage(message, 'user');
        chatMessage.value = '';

        // 确保当前模式会话存在，并保存用户消息
        const mode = isOrganizeMode ? 'organize' : 'query';
        let sessionId = isOrganizeMode ? currentOrganizeSessionId : currentQuerySessionId;
        if (!sessionId) {
            sessionId = await ensureActiveSession(mode);
        }
        try { await saveMessage(sessionId, 'user', message, mode); } catch (_) {}

        const token = localStorage.getItem('token');
        if (!token) return;

        try {
            // 查询模式已统一为流式整理（SSE）
            if (false) {
                const resp = await fetch(`${apiBaseUrl}/api/v1/documents/search`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({ query: message, limit: 10, score_threshold: 0.0 })
                });
                if (!resp.ok) {
                    let msg = '';
                    try { msg = (await resp.json())?.detail || ''; } catch (_) {}
                    appendMessage(`错误：搜索失败 ${msg || resp.status}`, 'bot');
                    return;
                }
                const data = await resp.json();
                const results = (data && Array.isArray(data.results)) ? data.results : [];
                renderQueryResults(results);
                return;
            }

            if (currentStreamController) {
                try { currentStreamController.abort(); } catch (_) {}
            }
            const controller = new AbortController();
            currentStreamController = controller;
            // 启动流式请求：根据模式选择接口
            const streamUrl = isOrganizeMode
                ? `${apiBaseUrl}/api/v1/llm/summarize`
                : `${apiBaseUrl}/api/v1/documents/search/answer/stream`;

            // 组织模式：在发送给大模型时加入最近5轮问答历史作为上下文
            let finalText = message;
            if (isOrganizeMode && chatWindow) {
                const historyTurns = getPreviousTurnsQA(5);  // 获取最近5轮问答
                if (historyTurns.length > 0) {
                    // 构建历史上下文（作为背景信息）
                    let historyContext = '\n\n---\n【对话历史上下文】\n';
                    historyTurns.forEach((turn, index) => {
                        const turnNum = index + 1;
                        historyContext += `第${turnNum}轮：`;
                        if (turn.user) {
                            historyContext += `用户问：${turn.user} | `;
                        }
                        if (turn.bot) {
                            historyContext += `回答：${turn.bot}`;
                        }
                        historyContext += '\n';
                    });
                    
                    // 将当前请求作为主体，历史作为上下文补充
                    finalText = `${message}${historyContext}
请基于上述主要内容进行详细的知识整理，结合历史对话上下文理解背景。需要包含：
1. 总体概述
2. 详细内容分析
3. 关键要点归纳
4. 总结与建议`;
                }
            }

            const bodyPayload = isOrganizeMode
                ? { text: finalText }
                : { query: message, limit: 5, score_threshold: 0.0 };
            const response = await fetch(streamUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                    'Accept': 'text/event-stream'
                },
                body: JSON.stringify(bodyPayload),
                signal: controller.signal,
                cache: 'no-store'
            });

            // 非流式回退：如果后端未返回 SSE，则读 JSON 一次性展示
            const contentType = response.headers.get('content-type') || '';
            if (!response.ok) {
                appendMessage('错误：无法获取整理结果。', 'bot');
                currentStreamController = null;
                return;
            }
            if (!response.body || !contentType.includes('text/event-stream')) {
                try {
                    const data = await response.json();
                    if (data && typeof data.answer === 'string') {
                        renderBotAnswerWithSources(data.answer, data.results || []);
                        try { await saveMessage(sessionId, 'bot', data.answer, mode); } catch (_) {}
                        currentStreamController = null;
                        return;
                    }
                    // 总结模式的非流式回退：直接显示文本
                    if (isOrganizeMode && typeof data?.text === 'string') {
                        renderBotAnswerWithSources(data.text, []);
                        try { await saveMessage(sessionId, 'bot', data.text, mode); } catch (_) {}
                        currentStreamController = null;
                        return;
                    }
                } catch (_) {}
                appendMessage('错误：后端未提供流式数据。', 'bot');
                currentStreamController = null;
                return;
            }

            // 创建可更新的机器人消息气泡
            const ui = startStreamingBotMessage();

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';
            let doneEventReceived = false;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });

                // 解析SSE帧 (以\n\n分隔)
                while (true) {
                    const sepIndex = buffer.indexOf('\n\n');
                    if (sepIndex === -1) break;
                    const rawEvent = buffer.slice(0, sepIndex);
                    buffer = buffer.slice(sepIndex + 2);

                    const lines = rawEvent.split('\n').filter(Boolean);
                    let eventName = 'message';
                    const dataLines = [];
                    for (const ln of lines) {
                        if (ln.startsWith('event:')) {
                            eventName = ln.slice(6).trim();
                        } else if (ln.startsWith('data:')) {
                            dataLines.push(ln.slice(5).trim());
                        }
                    }
                    const dataStr = dataLines.join('\n');

                    try {
                        if (eventName === 'sources') {
                            const sources = JSON.parse(dataStr);
                            setStreamingBotSources(ui, sources);
                        } else if (eventName === 'delta') {
                            // 尝试JSON解析（后端已JSON编码），失败则直接追加字符串
                            let delta;
                            try { delta = JSON.parse(dataStr); } catch (_) { delta = dataStr; }
                            updateStreamingBotMessage(ui, delta);
                        } else if (eventName === 'done') {
                            doneEventReceived = true;
                            finishStreamingBotMessage(ui);
                            const raw = (ui.contentTextElement && ui.contentTextElement.dataset && ui.contentTextElement.dataset.rawText) || '';
                            if (raw.trim()) { try { await saveMessage(sessionId, 'bot', raw, mode); } catch (_) {} }
                        } else if (eventName === 'error') {
                            const err = JSON.parse(dataStr);
                            updateStreamingBotMessage(ui, `\n[错误] ${err?.message || '流式处理失败'}`);
                            finishStreamingBotMessage(ui);
                            const raw = (ui.contentTextElement && ui.contentTextElement.dataset && ui.contentTextElement.dataset.rawText) || '';
                            if (raw.trim()) { try { await saveMessage(sessionId, 'bot', raw); } catch (_) {} }
                        }
                    } catch (e) {
                        // 任意解析错误，忽略该帧并继续
                        console.warn('SSE parse error:', e);
                    }
                }
            }

            if (!doneEventReceived) {
                finishStreamingBotMessage(ui);
                const raw = (ui.contentTextElement && ui.contentTextElement.dataset && ui.contentTextElement.dataset.rawText) || '';
                if (raw.trim()) { try { await saveMessage(sessionId, 'bot', raw, mode); } catch (_) {} }
            }
        } catch (error) {
            console.error('Chat error:', error);
            if (error && error.name === 'AbortError') {
                appendMessage('生成已取消。', 'bot');
            } else {
                appendMessage('错误：聊天过程中发生异常。', 'bot');
            }
        } finally {
            currentStreamController = null;
        }
    }

    // 提取最近N轮问答：跳过当前刚刚追加的用户消息，获取之前的问答对
    function getPreviousTurnsQA(maxTurns = 5) {
        const items = Array.from(chatWindow.querySelectorAll('.chat-message'));
        const turns = [];  // 存储问答对，每个对象包含 { user, bot }
        
        let skippedLatestUser = false;
        let currentTurn = null;
        
        // 从后向前遍历，收集问答对
        for (let i = items.length - 1; i >= 0 && turns.length < maxTurns; i--) {
            const el = items[i];
            
            if (el.classList.contains('user-message')) {
                // 跳过刚刚发送的当前用户消息
                if (!skippedLatestUser) {
                    skippedLatestUser = true;
                    continue;
                }
                
                // 开始一个新的问答轮
                const textEl = el.querySelector('.message-content');
                const userText = (textEl ? textEl.textContent : el.textContent || '').trim();
                
                // 如果当前有未完成的turn（只有bot），先保存它
                if (currentTurn && currentTurn.bot) {
                    turns.push(currentTurn);
                }
                
                // 创建新的turn
                currentTurn = { user: userText, bot: null };
                
            } else if (el.classList.contains('bot-message')) {
                // 获取机器人回复
                const textEl = el.querySelector('.message-text') || el.querySelector('.message-content');
                const raw = (textEl && textEl.dataset && textEl.dataset.rawText) || '';
                const botText = (raw || (textEl ? textEl.textContent : el.textContent || '')).trim();
                
                if (currentTurn && currentTurn.user) {
                    // 如果当前turn已有user，添加bot并保存
                    currentTurn.bot = botText;
                    turns.push(currentTurn);
                    currentTurn = null;
                } else {
                    // 如果还没有user，先保存bot
                    currentTurn = { user: null, bot: botText };
                }
            }
        }
        
        // 处理最后一个turn（如果有）
        if (currentTurn && turns.length < maxTurns) {
            turns.push(currentTurn);
        }
        
        // 返回的是从旧到新的顺序，所以需要reverse
        return turns.reverse();
    }

    // 安全地将文本中的换行渲染为 <br>，避免 XSS
    function escapeHTML(str) {
        return String(str || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function setContentWithNewlines(el, text) {
        const safe = escapeHTML(text || '');
        // 统一换行为 \n，并将字面字符串中的 \n/\r\n 也归一化
        const normalized = safe
            .replace(/\r\n|\r/g, '\n')
            .replace(/\\r\\n|\\n|\\r/g, '\n');

        // 以两个及以上换行切分为自然段；段内的单个换行用 <br>
        const paragraphs = normalized.split(/\n{2,}/);
        const html = paragraphs
            .map(p => p.replace(/\n/g, '<br>'))
            .join('</p><p>');

        el.innerHTML = `<p>${html}</p>`;
    }

    // 限制前端显示的最大长度（不影响原始内容保存）
    function truncateForDisplay(text, maxLen = 2000) {
        const str = String(text || '');
        if (str.length <= maxLen) return str;
        return str.slice(0, maxLen) + '…';
    }

    function appendMessage(content, sender) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('chat-message', `${sender}-message`);

        const contentElement = document.createElement('div');
        contentElement.classList.add('message-content');
        setContentWithNewlines(contentElement, content);

        messageElement.appendChild(contentElement);
        chatWindow.appendChild(messageElement);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    // 渲染查询模式下的结果列表（非流式）
    function renderQueryResults(results) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('chat-message', 'bot-message');

        const contentElement = document.createElement('div');
        contentElement.classList.add('message-content');
        const header = document.createElement('div');
        header.textContent = results.length > 0 ? `为你检索到 ${results.length} 条相关片段：` : '未检索到相关片段。';
        contentElement.appendChild(header);

        if (results.length > 0) {
            const list = document.createElement('div');
            list.classList.add('rag-sources');
            list.style.display = 'block';
            results.slice(0, 10).forEach((r, idx) => {
                const item = document.createElement('div');
                item.classList.add('rag-source-item');

                const title = document.createElement('div');
                title.classList.add('rag-source-title');
                title.textContent = `[片段${idx + 1}] ${r.title || '未命名'} (score: ${(r.score ?? 0).toFixed(3)})`;

                const snippet = document.createElement('div');
                snippet.classList.add('rag-source-snippet');
                const content = (r.content || '').replace(/\s+/g, ' ').trim();
                snippet.textContent = content.length > 260 ? `${content.slice(0, 260)}…` : content;

                item.appendChild(title);
                item.appendChild(snippet);
                list.appendChild(item);
            });
            contentElement.appendChild(list);
        }

        messageElement.appendChild(contentElement);
        chatWindow.appendChild(messageElement);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    // 渲染带有RAG来源折叠的机器人回复
    function renderBotAnswerWithSources(answer, results) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('chat-message', 'bot-message');

        const contentElement = document.createElement('div');
        contentElement.classList.add('message-content');
        // 使用内层文本容器，避免后续元素（如检索来源按钮）被覆盖
        const contentTextElement = document.createElement('div');
        contentTextElement.classList.add('message-text');
        // 保存完整的原始文本，显示时也使用全文
        contentTextElement.dataset.rawText = String(answer || '');
        setContentWithNewlines(contentTextElement, answer);  // 显示完整内容，不截断
        contentElement.appendChild(contentTextElement);

        // 底部按钮：组织模式改为“保存为知识文件”，查询模式为“显示检索来源”
        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.classList.add('rag-toggle');
        if (isOrganizeMode) {
            toggleBtn.textContent = '保存为知识文件';
        } else {
            toggleBtn.textContent = '显示检索来源';
        }

        // 折叠内容容器
        const sourcesContainer = document.createElement('div');
        sourcesContainer.classList.add('rag-sources');
        sourcesContainer.style.display = 'none';

        // 构建来源列表（仅查询模式展示）
        if (!isOrganizeMode) {
            if (results && results.length > 0) {
                results.slice(0, 10).forEach((r, idx) => {
                    const item = document.createElement('div');
                    item.classList.add('rag-source-item');

                    const titleEl = document.createElement('div');
                    titleEl.classList.add('rag-source-title');
                    titleEl.textContent = `[来源${idx + 1}] ${r.title || '未命名'} (score: ${(r.score ?? 0).toFixed(3)})`;

                    const snippet = document.createElement('div');
                    snippet.classList.add('rag-source-snippet');
                    const content = (r.content || '').replace(/\s+/g, ' ').trim();
                    snippet.textContent = content.length > 260 ? `${content.slice(0, 260)}…` : content;

                    item.appendChild(titleEl);
                    item.appendChild(snippet);
                    sourcesContainer.appendChild(item);
                });
            } else {
                const empty = document.createElement('div');
                empty.classList.add('rag-source-empty');
                empty.textContent = '未检索到来源片段。';
                sourcesContainer.appendChild(empty);
            }
        }

        // 交互逻辑：组织模式保存，查询模式切换来源
        if (isOrganizeMode) {
            toggleBtn.addEventListener('click', async () => {
                const token = localStorage.getItem('token');
                if (!token) { alert('请先登录'); return; }
                try {
                    const resp = await fetch(`${apiBaseUrl}/api/v1/documents/create/auto_title`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({
                            text: answer,
                            title: null,
                            source_url: currentSourceMeta.url || null
                        })
                    });
                    if (!resp.ok) {
                        let msg = '';
                        try { msg = (await resp.json())?.detail || ''; } catch (_) {}
                        alert(`保存失败：${msg || resp.status}`);
                        return;
                    }
                    const data = await resp.json();
                    // 保存成功后刷新左侧文档列表
                    try { await fetchDocuments(); } catch (e) { console.warn('刷新文档列表失败:', e); }
                    alert(`已保存到知识库：${data.title}`);
                } catch (e) {
                    console.error('Save knowledge error:', e);
                    alert('保存知识文件时出现错误。');
                }
            });
        } else {
            toggleBtn.addEventListener('click', () => {
                const isHidden = sourcesContainer.style.display === 'none';
                sourcesContainer.style.display = isHidden ? 'block' : 'none';
                toggleBtn.textContent = isHidden ? '收起检索来源' : '显示检索来源';
            });
        }

        // 简化结构：气泡、按钮、来源模块并列（按钮和来源为独立前端块）
        messageElement.appendChild(contentElement);
        messageElement.appendChild(toggleBtn);
        // 仅在查询模式下附加来源容器
        if (!isOrganizeMode) {
            messageElement.appendChild(sourcesContainer);
        }
        chatWindow.appendChild(messageElement);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    // 开始一个可增量更新的机器人消息
    function startStreamingBotMessage() {
        const messageElement = document.createElement('div');
        messageElement.classList.add('chat-message', 'bot-message');

        const contentElement = document.createElement('div');
        contentElement.classList.add('message-content');
        // 使用内层文本容器承载内容，避免覆盖其他子元素
        const contentTextElement = document.createElement('div');
        contentTextElement.classList.add('message-text');
        contentTextElement.textContent = '';
        // 原始文本缓冲，用于正确渲染换行
        contentTextElement.dataset.rawText = '';
        contentElement.appendChild(contentTextElement);

        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.classList.add('rag-toggle');
        toggleBtn.textContent = isOrganizeMode ? '保存为知识文件' : '显示检索来源';

        const sourcesContainer = document.createElement('div');
        sourcesContainer.classList.add('rag-sources');
        sourcesContainer.style.display = 'none';

        if (isOrganizeMode) {
            toggleBtn.addEventListener('click', async () => {
                const token = localStorage.getItem('token');
                if (!token) { alert('请先登录'); return; }
                const raw = (contentTextElement && contentTextElement.dataset.rawText) || '';
                if (!raw.trim()) { alert('暂无可保存内容'); return; }
                try {
                    const resp = await fetch(`${apiBaseUrl}/api/v1/documents/create/auto_title`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({
                            text: raw,
                            title: null,
                            source_url: currentSourceMeta.url || null
                        })
                    });
                    if (!resp.ok) {
                        let msg = '';
                        try { msg = (await resp.json())?.detail || ''; } catch (_) {}
                        alert(`保存失败：${msg || resp.status}`);
                        return;
                    }
                    const data = await resp.json();
                    // 保存成功后刷新左侧文档列表
                    try { await fetchDocuments(); } catch (e) { console.warn('刷新文档列表失败:', e); }
                    alert(`已保存到知识库：${data.title}`);
                } catch (e) {
                    console.error('Save knowledge error:', e);
                    alert('保存知识文件时出现错误。');
                }
            });
        } else {
            toggleBtn.addEventListener('click', () => {
                const isHidden = sourcesContainer.style.display === 'none';
                sourcesContainer.style.display = isHidden ? 'block' : 'none';
                toggleBtn.textContent = isHidden ? '收起检索来源' : '显示检索来源';
            });
        }

        // 简化结构：气泡、按钮、来源模块并列（按钮和来源为独立前端块）
        messageElement.appendChild(contentElement);
        messageElement.appendChild(toggleBtn);
        // 仅在查询模式下附加来源容器
        if (!isOrganizeMode) {
            messageElement.appendChild(sourcesContainer);
        }
        chatWindow.appendChild(messageElement);
        chatWindow.scrollTop = chatWindow.scrollHeight;

        return { messageElement, contentElement, contentTextElement, toggleBtn, sourcesContainer };
    }

    // 增量更新机器人消息内容
    function updateStreamingBotMessage(ui, deltaText) {
        let delta;
        if (typeof deltaText === 'string') {
            delta = deltaText;
        } else if (deltaText && typeof deltaText === 'object') {
            delta = deltaText.text || deltaText.delta || deltaText.content || deltaText.message || '';
        } else {
            delta = String(deltaText || '');
        }
        const prev = (ui.contentTextElement && ui.contentTextElement.dataset.rawText) || '';
        const next = prev + delta;
        if (ui.contentTextElement) {
            ui.contentTextElement.dataset.rawText = next;
            // 显示完整内容，不截断
            setContentWithNewlines(ui.contentTextElement, next);
        }
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    // 设置检索来源内容（供折叠展示）
    function setStreamingBotSources(ui, results) {
        const container = ui.sourcesContainer;
        container.innerHTML = '';
        if (Array.isArray(results) && results.length > 0) {
            results.slice(0, 10).forEach((r, idx) => {
                const item = document.createElement('div');
                item.classList.add('rag-source-item');

                const title = document.createElement('div');
                title.classList.add('rag-source-title');
                title.textContent = `[来源${idx + 1}] ${r.title || '未命名'} (score: ${(r.score ?? 0).toFixed(3)})`;

                item.appendChild(title);

                // 图片类型：优先渲染缩略图，点击可查看大图
                if (r.content_type === 'image' && (r.thumbnail_url || r.image_url)) {
                    const imgWrap = document.createElement('div');
                    imgWrap.classList.add('rag-source-image-wrap');

                    const img = document.createElement('img');
                    img.classList.add('rag-source-thumbnail');
                    img.src = r.thumbnail_url || r.image_url;
                    img.alt = r.title || '图片';
                    img.loading = 'lazy';
                    img.title = '点击查看大图';
                    img.style.cssText = 'max-width:160px;max-height:120px;cursor:pointer;border-radius:4px;border:1px solid #ddd;margin-top:6px;';
                    if (r.image_url) {
                        img.addEventListener('click', () => window.open(r.image_url, '_blank'));
                    }
                    imgWrap.appendChild(img);
                    item.appendChild(imgWrap);

                    // 图片描述（captions）作为补充文字
                    const content = (r.content || '').replace(/\s+/g, ' ').trim();
                    if (content) {
                        const caption = document.createElement('div');
                        caption.classList.add('rag-source-snippet');
                        caption.style.cssText = 'font-size:12px;color:#888;margin-top:4px;';
                        caption.textContent = content.length > 120 ? `${content.slice(0, 120)}…` : content;
                        item.appendChild(caption);
                    }
                } else {
                    const snippet = document.createElement('div');
                    snippet.classList.add('rag-source-snippet');
                    const content = (r.content || '').replace(/\s+/g, ' ').trim();
                    snippet.textContent = content.length > 260 ? `${content.slice(0, 260)}…` : content;
                    item.appendChild(snippet);
                }

                container.appendChild(item);
            });
        } else {
            const empty = document.createElement('div');
            empty.classList.add('rag-source-empty');
            empty.textContent = '未检索到来源片段。';
            container.appendChild(empty);
        }
    }

    // 结束流式消息（可用于做收尾或样式变更）
    function finishStreamingBotMessage(ui) {
        // 当前简单实现无需额外处理，保留占位以便后续增强
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    // --- Event Listeners ---
    // 登录和注册按钮
    loginBtn.addEventListener('click', (e) => { e.preventDefault(); loginUser(); });
    registerBtn.addEventListener('click', (e) => { e.preventDefault(); registerUser(); });
    
    // 邮箱登录链接
    const forgotUsernameEl = document.getElementById('forgot-username');
    if (forgotUsernameEl) {
        forgotUsernameEl.addEventListener('click', (e) => {
            e.preventDefault();
            // 切换到邮箱验证码登录表单
            loginForm.style.display = 'none';
            registerForm.style.display = 'none';
            if (emailOtpLoginForm) {
                emailOtpLoginForm.style.display = 'block';
            }
        });
    }
    // 文档上传和发送聊天
    uploadBtn.addEventListener('click', uploadDocument);
    sendChatBtn.addEventListener('click', sendChatMessage);
    // 返回左栏文档列表
    backToDocsBtn.addEventListener('click', () => {
        documentViewer.style.display = 'none';
        // 不再设置documentList.style.display，让CSS完全控制
        // 不再设置uploadForm.style.display，让CSS完全控制
    });
    if (historyToggle) {
        historyToggle.addEventListener('click', async () => {
            const showing = historyPanel && historyPanel.style.display === 'block';
            if (historyPanel) {
                historyPanel.style.display = showing ? 'none' : 'block';
                historyPanel.setAttribute('aria-hidden', String(showing));
            }
            // 在面板显示后加载会话列表（会自动滚动到底部）
            if (!showing) { await loadSessionList(); }
        });
    }
    
    if (uploadSourceBtn) uploadSourceBtn.addEventListener('click', openSourceModal);
    // 模式选择：标题可选框互斥，切换高亮并联动“上传来源”按钮
    function setMode(isOrganize) {
        isOrganizeMode = !!isOrganize;
        if (uploadSourceBtn) uploadSourceBtn.style.display = isOrganizeMode ? 'inline-block' : 'none';
        if (tabQuery && tabOrganize) {
            tabQuery.classList.toggle('active', !isOrganizeMode);
            tabQuery.setAttribute('aria-selected', String(!isOrganizeMode));
            tabOrganize.classList.toggle('active', isOrganizeMode);
            tabOrganize.setAttribute('aria-selected', String(isOrganizeMode));
        }
        if (chatMessage) {
            chatMessage.placeholder = isOrganizeMode
                ? '输入需要梳理的问题，例如：总结最近上传文档要点'
                : '输入问题，返回大模型整合后的答案';
        }
        // 切换模式时清空窗口，避免内容混杂（但保留历史按钮和面板）
        if (chatWindow) {
            // 清空所有消息
            const messages = chatWindow.querySelectorAll('.chat-message');
            messages.forEach(msg => msg.remove());
        }
        // 切换模式时不再加载历史，等待用户点击历史按钮
    }

    // 初始化模式UI（避免未定义导致脚本中断）
    function updateModeUI() {
        // 默认进入“知识查询”模式
        setMode(false);
    }
    if (tabQuery || tabOrganize) {
        setMode(false); // 默认“知识查询”
        if (tabQuery) tabQuery.addEventListener('click', () => { setMode(false); updateLanguage(currentLang); });
        if (tabOrganize) tabOrganize.addEventListener('click', () => { setMode(true); updateLanguage(currentLang); });
    }

    // 事件委托：提升健壮性，避免某些情况下点击未绑定或被覆盖
    const modeTabs = document.getElementById('mode-tabs');
    if (modeTabs) {
        modeTabs.addEventListener('click', (e) => {
            const target = e.target.closest('.mode-tab');
            if (!target) return;
            const isOrganize = target.id === 'tab-organize';
            setMode(isOrganize);
        });
        // 键盘可访问：回车/空格切换
        modeTabs.addEventListener('keydown', (e) => {
            if (!(e.key === 'Enter' || e.key === ' ')) return;
            const target = e.target.closest('.mode-tab');
            if (!target) return;
            e.preventDefault();
            const isOrganize = target.id === 'tab-organize';
            setMode(isOrganize);
        });
    }
    if (sourceModalClose) sourceModalClose.addEventListener('click', closeSourceModal);
    if (tabUrlBtn) tabUrlBtn.addEventListener('click', () => setActiveSourceTab('url'));
    if (tabFileBtn) tabFileBtn.addEventListener('click', () => setActiveSourceTab('file'));
    if (submitUrlBtn) submitUrlBtn.addEventListener('click', submitUrlSource);
    if (submitFileBtn) submitFileBtn.addEventListener('click', submitFileSource);

    chatMessage.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendChatMessage();
        }
    });

    documentList.addEventListener('click', (e) => {
        const target = e.target;
        if (target.classList.contains('delete-icon')) {
            e.stopPropagation();
            const docId = target.dataset.docId;
            deleteDocumentById(docId);
            return;
        }
        if (target.classList.contains('document-item') || target.classList.contains('document-title')) {
            const parent = target.closest('.document-item');
            const docId = (parent ? parent.dataset.docId : target.dataset.docId);
            fetchDocumentContent(docId);
        }
    });

    deletedDocumentList.addEventListener('click', (e) => {
        const target = e.target;
        const docId = target.dataset.docId;
        if (target.classList.contains('restore-btn')) {
            restoreDocumentById(docId);
        } else if (target.classList.contains('purge-btn')) {
            purgeDocumentById(docId);
        }
    });

    openTrashBtn.addEventListener('click', () => {
        console.log('UI: open trash clicked');
        showTrashList();
        fetchDeletedDocuments();
    });

    backToDocsFromTrashBtn.addEventListener('click', () => {
        showDocumentList();
        fetchDocuments();
    });

    function initApp() {
        // 单用户模式：跳过登录，直接进入主界面
        // 设置占位 token，确保所有 API 调用正常通过 token 检查
        localStorage.setItem('token', 'single-user-mode');
        authContainer.style.display = 'none';
        mainContainer.style.display = 'flex';
        // 强制初始化document-management为flex布局，防止浏览器缓存造成的block样式
        const docMgmt = document.getElementById('document-management');
        if (docMgmt) docMgmt.style.display = 'flex';
        // 不再设置uploadForm的display，让CSS完全控制
        const languageToggle = document.querySelector('.language-toggle');
        if (languageToggle) languageToggle.style.display = 'none';
        // 初始化模式UI
        updateModeUI();
        // 直接加载用户信息和文档
        fetchCurrentUser();
    }

    initApp();
    // 页面关闭前尝试关闭会话
    window.addEventListener('beforeunload', () => { try { closeActiveSessions(); } catch (_) {} });
    
    // ========== 知识图谱可视化功能 ==========
    initKnowledgeGraph();
});

// 知识图谱可视化类 (类似 Obsidian)
class KnowledgeGraphVisualizer {
    constructor() {
        this.canvas = document.getElementById('kg-canvas');
        this.ctx = this.canvas?.getContext('2d');
        this.nodes = [];
        this.edges = [];
        this.animationId = null;
        this.isDragging = false;
        this.draggedNode = null;
        this.hoveredNode = null;
        this.transform = { x: 0, y: 0, scale: 1 };
        
        // 节点颜色映射 - 根据类型设置不同颜色
        this.nodeColors = {
            'Document': '#667eea',      // 文档 - 紫色
            'Person': '#FF6B6B',        // 人物 - 红色
            'Organization': '#4ECDC4',  // 组织 - 青色
            'Location': '#95E1D3',      // 地点 - 绿色
            'Concept': '#F38181',       // 概念 - 粉色
            'Event': '#AA96DA',         // 事件 - 淡紫
            'Entity': '#A8D8EA'         // 实体 - 蓝色
        };
        
        // 力导向布局参数
        this.forceParams = {
            repulsion: 800,           // 排斥力
            attraction: 0.05,         // 吸引力
            damping: 0.9,             // 阻尼系数
            centerForce: 0.01,        // 中心力
            maxVelocity: 5            // 最大速度
        };
        
        this.initEvents();
    }
    
    initEvents() {
        if (!this.canvas) return;
        
        // 鼠标事件
        this.canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mouseup', () => this.handleMouseUp());
        this.canvas.addEventListener('wheel', (e) => this.handleWheel(e), { passive: false });
        
        // 窗口大小变化
        window.addEventListener('resize', () => this.resize());
    }
    
    resize() {
        if (!this.canvas) return;
        const container = this.canvas.parentElement;
        this.canvas.width = container.clientWidth;
        this.canvas.height = container.clientHeight;
        this.render();
    }
    
    loadData(data) {
        // 确保数据有效
        if (!data || !Array.isArray(data.nodes)) {
            console.error('Invalid graph data:', data);
            this.nodes = [];
            this.edges = [];
            return;
        }
        
        const width = this.canvas?.width || 800;
        const height = this.canvas?.height || 600;
        
        // 初始化节点位置 - 使用圆形分布，看起来更美观
        this.nodes = data.nodes.map((node, i) => {
            const angle = (i / Math.max(data.nodes.length, 1)) * Math.PI * 2;
            const radius = Math.min(width, height) * 0.3;
            return {
                ...node,
                x: Math.cos(angle) * radius + width / 2,
                y: Math.sin(angle) * radius + height / 2,
                vx: 0,
                vy: 0,
                radius: 15 + Math.min((node.label || node.name || 'Node').length * 1.5, 25),
                color: this.getNodeColor(node.type || 'Entity')
            };
        });
        
        this.edges = Array.isArray(data.edges) ? data.edges : [];
        
        // 初始化力导向布局
        this.initForceLayout();
    }
    
    getNodeColor(type) {
        return this.nodeColors[type] || this.nodeColors['Entity'];
    }
    
    initForceLayout() {
        // 如果没有节点或边，直接返回
        if (this.nodes.length === 0) {
            console.log('No nodes to layout');
            return;
        }
        
        const width = this.canvas?.width || 800;
        const height = this.canvas?.height || 600;
        const centerX = width / 2;
        const centerY = height / 2;
        
        // 使用配置的参数
        const { repulsion, attraction, damping, centerForce, maxVelocity } = this.forceParams;
        
        // 执行多次迭代使布局稳定
        const iterations = 150;
        for (let iter = 0; iter < iterations; iter++) {
            // 计算斥力（所有节点之间）
            for (let i = 0; i < this.nodes.length; i++) {
                for (let j = i + 1; j < this.nodes.length; j++) {
                    const dx = this.nodes[j].x - this.nodes[i].x;
                    const dy = this.nodes[j].y - this.nodes[i].y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    
                    // 斥力与距离平方成反比
                    const force = repulsion / (dist * dist);
                    
                    const fx = (dx / dist) * force;
                    const fy = (dy / dist) * force;
                    
                    this.nodes[i].vx -= fx;
                    this.nodes[i].vy -= fy;
                    this.nodes[j].vx += fx;
                    this.nodes[j].vy += fy;
                }
            }
            
            // 计算引力（有边的节点之间）
            for (const edge of this.edges) {
                const source = this.nodes.find(n => n.id === edge.source);
                const target = this.nodes.find(n => n.id === edge.target);
                
                if (source && target) {
                    const dx = target.x - source.x;
                    const dy = target.y - source.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    
                    // 引力与距离成正比（弹簧效果）
                    const force = dist * attraction;
                    
                    const fx = (dx / dist) * force;
                    const fy = (dy / dist) * force;
                    
                    source.vx += fx;
                    source.vy += fy;
                    target.vx -= fx;
                    target.vy -= fy;
                }
            }
            
            // 中心吸引力（防止节点飞散）
            for (const node of this.nodes) {
                const dx = centerX - node.x;
                const dy = centerY - node.y;
                node.vx += dx * centerForce * 0.1;
                node.vy += dy * centerForce * 0.1;
            }
            
            // 更新位置并限制速度
            for (const node of this.nodes) {
                // 应用阻尼
                node.vx *= damping;
                node.vy *= damping;
                
                // 限制最大速度
                const speed = Math.sqrt(node.vx * node.vx + node.vy * node.vy);
                if (speed > maxVelocity) {
                    node.vx = (node.vx / speed) * maxVelocity;
                    node.vy = (node.vy / speed) * maxVelocity;
                }
                
                // 更新位置
                node.x += node.vx;
                node.y += node.vy;
                
                // 边界约束（保持在画布内）
                const margin = node.radius + 10;
                node.x = Math.max(margin, Math.min(width - margin, node.x));
                node.y = Math.max(margin, Math.min(height - margin, node.y));
            }
        }
    }
    
    render() {
        if (!this.ctx || !this.canvas) return;
        
        const { width, height } = this.canvas;
        this.ctx.clearRect(0, 0, width, height);
        
        // 绘制背景网格（类似 Obsidian）
        this.drawGrid(width, height);
        
        this.ctx.save();
        this.ctx.translate(width / 2 + this.transform.x, height / 2 + this.transform.y);
        this.ctx.scale(this.transform.scale, this.transform.scale);
        
        // 绘制边
        for (const edge of this.edges) {
            const source = this.nodes.find(n => n.id === edge.source);
            const target = this.nodes.find(n => n.id === edge.target);
            
            if (source && target) {
                // 根据边的权重设置透明度
                const weight = edge.weight || 1.0;
                const opacity = Math.min(0.6, 0.2 + weight * 0.1);
                
                this.ctx.beginPath();
                this.ctx.moveTo(source.x, source.y);
                this.ctx.lineTo(target.x, target.y);
                this.ctx.strokeStyle = `rgba(150, 150, 180, ${opacity})`;
                this.ctx.lineWidth = 1.5 + weight * 0.5;
                this.ctx.stroke();
            }
        }
        
        // 绘制节点
        for (const node of this.nodes) {
            const color = node.color || this.getNodeColor(node.type || 'Entity');
            
            // 节点光晕效果
            this.ctx.beginPath();
            this.ctx.arc(node.x, node.y, node.radius + 5, 0, Math.PI * 2);
            this.ctx.fillStyle = `${color}33`; // 20% 透明度
            this.ctx.fill();
            
            // 节点阴影
            this.ctx.beginPath();
            this.ctx.arc(node.x + 2, node.y + 2, node.radius, 0, Math.PI * 2);
            this.ctx.fillStyle = 'rgba(0, 0, 0, 0.15)';
            this.ctx.fill();
            
            // 节点本体 - 使用渐变填充
            const gradient = this.ctx.createRadialGradient(
                node.x - node.radius * 0.3,
                node.y - node.radius * 0.3,
                0,
                node.x,
                node.y,
                node.radius
            );
            gradient.addColorStop(0, this.lightenColor(color, 30));
            gradient.addColorStop(1, color);
            
            this.ctx.beginPath();
            this.ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
            this.ctx.fillStyle = gradient;
            this.ctx.fill();
            
            // 节点边框
            this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
            this.ctx.lineWidth = 2;
            this.ctx.stroke();
            
            // 节点标签
            this.ctx.fillStyle = 'white';
            this.ctx.font = 'bold 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            
            // 截断长文本，处理null值
            let label = node.label || node.name || node.id || 'Node';
            if (label && label.length > 12) {
                label = label.substring(0, 12) + '...';
            }
            
            // 添加文字阴影提高可读性
            this.ctx.shadowColor = 'rgba(0, 0, 0, 0.5)';
            this.ctx.shadowBlur = 3;
            this.ctx.fillText(label, node.x, node.y);
            this.ctx.shadowBlur = 0;
        }
        
        this.ctx.restore();
    }
    
    // 绘制背景网格
    drawGrid(width, height) {
        this.ctx.strokeStyle = 'rgba(200, 200, 220, 0.15)';
        this.ctx.lineWidth = 1;
        
        const gridSize = 40;
        
        // 垂直线
        for (let x = 0; x <= width; x += gridSize) {
            this.ctx.beginPath();
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, height);
            this.ctx.stroke();
        }
        
        // 水平线
        for (let y = 0; y <= height; y += gridSize) {
            this.ctx.beginPath();
            this.ctx.moveTo(0, y);
            this.ctx.lineTo(width, y);
            this.ctx.stroke();
        }
    }
    
    // 颜色变亮辅助函数
    lightenColor(color, percent) {
        const num = parseInt(color.replace('#', ''), 16);
        const amt = Math.round(2.55 * percent);
        const R = (num >> 16) + amt;
        const G = (num >> 8 & 0x00FF) + amt;
        const B = (num & 0x0000FF) + amt;
        return '#' + (
            0x1000000 +
            (R < 255 ? (R < 1 ? 0 : R) : 255) * 0x10000 +
            (G < 255 ? (G < 1 ? 0 : G) : 255) * 0x100 +
            (B < 255 ? (B < 1 ? 0 : B) : 255)
        ).toString(16).slice(1);
    }
    
    handleMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = (e.clientX - rect.left - this.canvas.width / 2 - this.transform.x) / this.transform.scale;
        const y = (e.clientY - rect.top - this.canvas.height / 2 - this.transform.y) / this.transform.scale;
        
        // 检查是否点击了节点
        for (const node of this.nodes) {
            const dist = Math.sqrt((x - node.x) ** 2 + (y - node.y) ** 2);
            if (dist < node.radius) {
                this.isDragging = true;
                this.draggedNode = node;
                break;
            }
        }
    }
    
    handleMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = (e.clientX - rect.left - this.canvas.width / 2 - this.transform.x) / this.transform.scale;
        const y = (e.clientY - rect.top - this.canvas.height / 2 - this.transform.y) / this.transform.scale;
        
        if (this.isDragging && this.draggedNode) {
            this.draggedNode.x = x;
            this.draggedNode.y = y;
            this.render();
        } else {
            // 检查悬停
            let hovered = null;
            for (const node of this.nodes) {
                const dist = Math.sqrt((x - node.x) ** 2 + (y - node.y) ** 2);
                if (dist < node.radius) {
                    hovered = node;
                    break;
                }
            }
            
            if (hovered !== this.hoveredNode) {
                this.hoveredNode = hovered;
                this.canvas.style.cursor = hovered ? 'pointer' : 'grab';
                this.render();
            }
        }
    }
    
    handleMouseUp() {
        this.isDragging = false;
        this.draggedNode = null;
    }
    
    handleWheel(e) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        this.transform.scale *= delta;
        this.transform.scale = Math.max(0.1, Math.min(5, this.transform.scale));
        this.render();
    }
    
    startAnimation() {
        const animate = () => {
            this.render();
            this.animationId = requestAnimationFrame(animate);
        };
        animate();
    }
    
    stopAnimation() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    }
}

// 初始化知识图谱功能 (类似 Obsidian)
function initKnowledgeGraph() {
    const kgCard = document.getElementById('kg-card');
    const kgViewContainer = document.getElementById('kg-view-container');
    const kgRefreshBtn = document.getElementById('kg-refresh-btn');
    const kgCloseBtn = document.getElementById('kg-close-btn');
    const kgTabs = document.querySelectorAll('.kg-tab');
    
    if (!kgCard || !kgViewContainer) return;
    
    let visualizer = null;
    let isKgViewActive = false;
    let currentTabType = 'documents'; // 当前显示的图谱类型
    
    // 加载图谱数据
    async function loadGraphData(type) {
        try {
            // 显示加载状态
            document.getElementById('kg-loading-overlay').style.display = 'flex';
            document.getElementById('kg-canvas').style.display = 'none';
            
            // 根据类型选择API端点
            let apiUrl;
            if (type === 'documents') {
                apiUrl = `${apiBaseUrl}/api/v1/documents/knowledge-graph/documents?limit=100`;
            } else if (type === 'entities') {
                apiUrl = `${apiBaseUrl}/api/v1/documents/knowledge-graph/entities?limit=200`;
            } else {
                apiUrl = `${apiBaseUrl}/api/v1/documents/knowledge-graph/full?limit=150`;
            }
            
            console.log(`Loading ${type} graph from:`, apiUrl);
            
            const response = await fetch(apiUrl, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });
            
            if (!response.ok) {
                throw new Error(`获取${type === 'documents' ? '文档' : type === 'entities' ? '实体' : ''}图谱失败 (${response.status})`);
            }
            
            const data = await response.json();
            console.log(`${type} graph data received:`, {
                total_nodes: data.total_nodes,
                total_edges: data.total_edges,
                nodes_sample: data.nodes?.slice(0, 3)
            });
            
            // 初始化可视化器
            if (!visualizer) {
                visualizer = new KnowledgeGraphVisualizer();
            }
            
            visualizer.loadData(data);
            
            // 等待容器渲染后调整画布大小
            setTimeout(() => {
                visualizer.resize();
                
                // 隐藏加载，显示画布
                document.getElementById('kg-loading-overlay').style.display = 'none';
                document.getElementById('kg-canvas').style.display = 'block';
                
                // 更新统计信息
                if (type === 'documents') {
                    document.getElementById('kg-doc-count').textContent = data.total_nodes || 0;
                    document.getElementById('kg-entity-count').textContent = '-';
                    document.getElementById('kg-relation-count').textContent = data.total_edges || 0;
                } else if (type === 'entities') {
                    document.getElementById('kg-doc-count').textContent = '-';
                    document.getElementById('kg-entity-count').textContent = data.total_nodes || 0;
                    document.getElementById('kg-relation-count').textContent = data.total_edges || 0;
                }
                
                // 开始渲染
                visualizer.startAnimation();
            }, 100);
            
            return true;
        } catch (error) {
            console.error(`加载${type}图谱失败:`, error);
            document.getElementById('kg-loading-overlay').innerHTML = `
                <p style="color: #667eea;">❌ 加载失败: ${error.message}</p>
                <p style="color: #6c757d; font-size: 14px; margin-top: 8px;">请确保Neo4j服务已启动并有数据</p>
            `;
            return false;
        }
    }
    
    // 点击知识图谱卡片 - 在下方显示图谱视图
    kgCard.addEventListener('click', async () => {
        if (isKgViewActive) {
            // 如果已经显示，滚动到图谱区域
            kgViewContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return;
        }
        
        isKgViewActive = true;
        currentTabType = 'documents'; // 默认显示文档图谱
        
        // 显示图谱视图（不隐藏卡片网格）
        kgViewContainer.style.display = 'flex';
        
        // 加载文档图谱
        await loadGraphData('documents');
        
        // 滚动到图谱区域
        kgViewContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    
    // 标签切换
    kgTabs.forEach(tab => {
        tab.addEventListener('click', async () => {
            // 移除所有active类
            kgTabs.forEach(t => t.classList.remove('active'));
            // 添加当前active类
            tab.classList.add('active');
            
            // 获取要切换的类型
            const newType = tab.getAttribute('data-type');
            
            if (newType !== currentTabType) {
                currentTabType = newType;
                await loadGraphData(newType);
            }
        });
    });
    
    // 刷新按钮
    kgRefreshBtn.addEventListener('click', async () => {
        if (!visualizer) return;
        
        // 重新加载当前类型的图谱
        await loadGraphData(currentTabType);
    });
    
    // 关闭按钮 - 隐藏图谱区域
    kgCloseBtn.addEventListener('click', () => {
        kgViewContainer.style.display = 'none';
        isKgViewActive = false;
        // 停止动画以节省资源
        if (visualizer && visualizer.stopAnimation) {
            visualizer.stopAnimation();
        }
    });
}