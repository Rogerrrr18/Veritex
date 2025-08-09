import './style.css'
import { ChatAPI } from './api.js'

class PaperSearchApp {
    constructor() {
        this.searchAPI = new ChatAPI()
        this.searchHistory = []
        this.isLoading = false
        this.storageKey = 'paper_search_chat_history'
        
        // Token管理配置
        this.tokenLimits = {
            soft: 3000,    // 软限制：开始提醒
            hard: 4000,    // 硬限制：必须截止
            window: 8      // 滑动窗口：保留最近8轮对话
        }
        this.currentTokenCount = 0
        
        this.initElements()
        this.bindEvents()
        this.loadChatHistory()
        this.updateTokenDisplay()
        this.checkAPIHealth()
    }
    
    initElements() {
        this.chatMessages = document.getElementById('chatMessages')
        this.messageInput = document.getElementById('messageInput')
        this.sendBtn = document.getElementById('sendBtn')
        this.clearBtn = document.getElementById('clearBtn')
        this.historyBtn = document.getElementById('historyBtn')
        
        // 历史记录管理相关元素
        this.historyModal = document.getElementById('historyModal')
        this.conversationModal = document.getElementById('conversationModal')
        this.modalBackdrop = document.getElementById('modalBackdrop')
        this.historyList = document.getElementById('historyList')
        this.historyStats = document.getElementById('historyStats')
        this.historySearch = document.getElementById('historySearch')
        this.sortOrder = document.getElementById('sortOrder')
        
        // 移除loadingOverlay引用
    }
    
    bindEvents() {
        // 发送按钮点击
        this.sendBtn.addEventListener('click', () => this.sendMessage())
        
        // 输入框事件
        this.messageInput.addEventListener('input', () => this.handleInputChange())
        this.messageInput.addEventListener('keydown', (e) => this.handleKeyDown(e))
        
        // 清空按钮
        this.clearBtn.addEventListener('click', () => this.clearChat())
        
        // 历史记录按钮
        this.historyBtn.addEventListener('click', () => this.openHistoryModal())
        
        // 模态框事件
        this.bindModalEvents()
        
        // 自动调整输入框高度
        this.messageInput.addEventListener('input', () => this.autoResizeTextarea())
    }
    
    handleInputChange() {
        const hasText = this.messageInput.value.trim().length > 0
        this.sendBtn.disabled = !hasText || this.isLoading
    }
    
    handleKeyDown(e) {
        // Ctrl+Enter 或 Shift+Enter 发送消息
        if (e.key === 'Enter' && (e.ctrlKey || e.shiftKey)) {
            e.preventDefault()
            this.sendMessage()
        }
        // 普通Enter键允许换行，不发送消息
    }
    
    autoResizeTextarea() {
        this.messageInput.style.height = 'auto'
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px'
    }
    
    async checkAPIHealth() {
        try {
            const health = await this.searchAPI.checkHealth()
            console.log('API健康状态:', health)
        } catch (error) {
            console.error('API连接失败:', error)
            this.showError('无法连接到后端服务，请检查后端是否启动')
        }
    }
    
    async sendMessage() {
        const message = this.messageInput.value.trim()
        if (!message || this.isLoading) return
        
        // 添加用户消息
        this.addMessage('user', message)
        this.messageInput.value = ''
        this.handleInputChange()
        this.autoResizeTextarea()
        
        // 设置加载状态（不显示蒙版）
        this.isLoading = true
        this.sendBtn.disabled = true
        this.messageInput.disabled = true
        
        try {
            // 在发送前检查并优化历史
            this.optimizeHistory()
            
            // 调用搜索API
            const response = await this.searchAPI.sendMessage(message, this.searchHistory)
            
            // 添加搜索结果
            this.addMessage('assistant', response.response)
            
            // 更新搜索历史
            this.searchHistory = response.history
            
            // 如果后端提供了token信息，使用后端数据更新显示
            if (response.token_info) {
                this.currentTokenCount = response.token_info.total_tokens
                console.log('后端Token信息:', response.token_info)
            }
            
        } catch (error) {
            console.error('发送消息失败:', error)
            this.addMessage('system', '抱歉，搜索论文时出现错误。请稍后再试。')
        } finally {
            this.isLoading = false
            this.sendBtn.disabled = this.messageInput.value.trim().length === 0
            this.messageInput.disabled = false
        }
    }
    
    addMessage(role, content, isWarning = false, warningLevel = null) {
        // 移除欢迎消息
        const welcomeMessage = this.chatMessages.querySelector('.welcome-message')
        if (welcomeMessage) {
            welcomeMessage.remove()
        }
        
        // 添加消息到DOM
        this.addMessageToDOM(role, content, null, true, isWarning, warningLevel)
        
        // 保存到localStorage（警告消息不保存）
        if (!isWarning) {
            this.saveChatHistory()
        }
        
        // 更新token显示
        this.updateTokenDisplay()
        
        // 滚动到底部
        this.scrollToBottom()
    }
    
    setLoading(loading) {
        this.isLoading = loading
        // 移除蒙版显示，只控制按钮状态
        this.sendBtn.disabled = loading || this.messageInput.value.trim().length === 0
        this.messageInput.disabled = loading
    }
    
    clearChat() {
        if (confirm('确定要清空搜索记录吗？')) {
            this.searchHistory = []
            this.chatMessages.innerHTML = `
                <div class="welcome-message">
                    <div class="welcome-icon">📚</div>
                    <h2>欢迎使用学术论文搜索系统</h2>
                    <p>基于LangGraph智能代理，支持多数据源论文搜索</p>
                </div>
            `
            // 清空本地存储
            this.clearChatHistory()
        }
    }
    
    showError(message) {
        this.addMessage('system', message)
    }
    
    scrollToBottom() {
        setTimeout(() => {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight
        }, 100)
    }
    
    // localStorage相关方法
    saveChatHistory() {
        try {
            const chatData = {
                messages: this.getChatMessages(),
                searchHistory: this.searchHistory,
                timestamp: new Date().toISOString()
            }
            localStorage.setItem(this.storageKey, JSON.stringify(chatData))
        } catch (error) {
            console.error('保存聊天记录失败:', error)
        }
    }
    
    loadChatHistory() {
        try {
            const savedData = localStorage.getItem(this.storageKey)
            if (savedData) {
                const chatData = JSON.parse(savedData)
                
                // 恢复搜索历史
                this.searchHistory = chatData.searchHistory || []
                
                // 恢复聊天消息
                if (chatData.messages && chatData.messages.length > 0) {
                    this.restoreChatMessages(chatData.messages)
                }
                
                console.log('已恢复聊天记录，共', chatData.messages?.length || 0, '条消息')
            }
        } catch (error) {
            console.error('加载聊天记录失败:', error)
            // 如果加载失败，清除损坏的数据
            this.clearChatHistory()
        }
    }
    
    getChatMessages() {
        const messages = []
        const messageElements = this.chatMessages.querySelectorAll('.message:not(.welcome-message)')
        
        messageElements.forEach(element => {
            const role = element.classList.contains('user-message') ? 'user' : 
                        element.classList.contains('assistant-message') ? 'assistant' : 'system'
            const content = element.querySelector('.message-content')?.textContent || ''
            const timestamp = element.querySelector('.message-timestamp')?.textContent || ''
            
            messages.push({
                role,
                content,
                timestamp
            })
        })
        
        return messages
    }
    
    restoreChatMessages(messages) {
        // 移除欢迎消息
        const welcomeMessage = this.chatMessages.querySelector('.welcome-message')
        if (welcomeMessage) {
            welcomeMessage.remove()
        }
        
        messages.forEach(message => {
            this.addMessageToDOM(message.role, message.content, message.timestamp, false) // 传递false禁用打字机效果
        })
        
        this.scrollToBottom()
    }
    
    addMessageToDOM(role, content, timestamp = null, useTyping = true, isWarning = false, warningLevel = null) {
        const messageDiv = document.createElement('div')
        messageDiv.className = `message ${role}-message`
        
        // 添加警告级别的CSS类
        if (isWarning && warningLevel) {
            messageDiv.classList.add(`token-warning-${warningLevel}`)
        }
        
        const avatar = document.createElement('div')
        avatar.className = 'message-avatar'
        avatar.textContent = role === 'user' ? '👤' : role === 'assistant' ? '🤖' : '⚠️'
        
        const content_div = document.createElement('div')
        content_div.className = 'message-content'
        
        // 为警告消息添加特殊样式
        if (isWarning) {
            content_div.classList.add('warning-message')
        }
        
        const timestampDiv = document.createElement('div')
        timestampDiv.className = 'message-timestamp'
        timestampDiv.textContent = timestamp || new Date().toLocaleTimeString()
        
        messageDiv.appendChild(avatar)
        messageDiv.appendChild(content_div)
        messageDiv.appendChild(timestampDiv)
        
        // 如果是关键警告，添加新对话按钮
        if (warningLevel === 'critical') {
            const actionDiv = document.createElement('div')
            actionDiv.className = 'warning-actions'
            
            const newChatBtn = document.createElement('button')
            newChatBtn.className = 'new-chat-btn'
            newChatBtn.textContent = '开启新对话'
            newChatBtn.onclick = () => this.startNewConversation()
            
            actionDiv.appendChild(newChatBtn)
            messageDiv.appendChild(actionDiv)
        }
        
        this.chatMessages.appendChild(messageDiv)
        
        // 对助手消息使用打字机效果（仅在useTyping为true时）
        if (role === 'assistant' && useTyping && !isWarning) {
            this.typeMessage(content_div, content)
        } else {
            // 用户消息、系统消息或禁用打字机效果时直接显示
            content_div.textContent = content
        }
    }
    
    async typeMessage(element, text) {
        element.textContent = ''
        
        // 处理包含表格或代码块的文本
        if (text.includes('|') || text.includes('```') || text.includes('\t')) {
            // 对于表格和代码块，使用较快的打字速度
            const chars = text.split('')
            
            for (let i = 0; i < chars.length; i++) {
                element.textContent += chars[i]
                
                // 动态滚动到底部
                this.scrollToBottom()
                
                // 较快的打字速度
                let delay = 5
                if (chars[i] === '\n') {
                    delay = 30
                } else if (/[，。！？；：,.\!\?\;\:]/.test(chars[i])) {
                    delay = 15
                }
                
                await new Promise(resolve => setTimeout(resolve, delay))
            }
        } else {
            // 普通文本使用正常打字速度
            const chars = text.split('')
            
            for (let i = 0; i < chars.length; i++) {
                element.textContent += chars[i]
                
                // 动态滚动到底部
                this.scrollToBottom()
                
                // 普通打字速度
                let delay = 20
                if (chars[i] === '\n') {
                    delay = 100
                } else if (/[，。！？；：,.\!\?\;\:]/.test(chars[i])) {
                    delay = 50
                }
                
                await new Promise(resolve => setTimeout(resolve, delay))
            }
        }
    }
    
    clearChatHistory() {
        try {
            localStorage.removeItem(this.storageKey)
            console.log('聊天记录已清空')
        } catch (error) {
            console.error('清空聊天记录失败:', error)
        }
    }
    
    // Token管理相关方法
    estimateTokens(text) {
        if (!text) return 0
        
        // 简单的token估算算法
        // 中文字符按1.5个token计算，英文单词按1.3个token计算
        const chineseChars = (text.match(/[\u4e00-\u9fff]/g) || []).length
        const englishWords = (text.match(/[a-zA-Z]+/g) || []).length
        const otherChars = text.length - chineseChars - englishWords
        
        return Math.ceil(chineseChars * 1.5 + englishWords * 1.3 + otherChars * 0.5)
    }
    
    calculateTotalTokens() {
        let totalTokens = 0
        
        // 计算历史对话的token数
        this.searchHistory.forEach(message => {
            totalTokens += this.estimateTokens(message.content || '')
        })
        
        // 计算当前显示消息的token数
        const messageElements = this.chatMessages.querySelectorAll('.message:not(.welcome-message)')
        messageElements.forEach(element => {
            const content = element.querySelector('.message-content')?.textContent || ''
            totalTokens += this.estimateTokens(content)
        })
        
        return totalTokens
    }
    
    updateTokenDisplay() {
        this.currentTokenCount = this.calculateTotalTokens()
        
        // 更新进度条（如果存在）
        const tokenProgress = document.getElementById('tokenProgress')
        const tokenInfo = document.getElementById('tokenInfo')
        
        if (tokenProgress) {
            const percentage = Math.min((this.currentTokenCount / this.tokenLimits.hard) * 100, 100)
            tokenProgress.style.width = `${percentage}%`
            
            // 根据token使用量改变颜色
            if (percentage < 50) {
                tokenProgress.className = 'token-progress-bar token-safe'
            } else if (percentage < 75) {
                tokenProgress.className = 'token-progress-bar token-warning'
            } else {
                tokenProgress.className = 'token-progress-bar token-danger'
            }
        }
        
        if (tokenInfo) {
            tokenInfo.textContent = `${this.currentTokenCount} / ${this.tokenLimits.hard} tokens`
        }
        
        // 检查是否需要显示提醒
        this.checkTokenLimits()
    }
    
    checkTokenLimits() {
        const percentage = (this.currentTokenCount / this.tokenLimits.hard) * 100
        
        if (percentage >= 90) {
            // 90%以上：强提醒
            this.showTokenWarning('critical', '对话即将达到长度限制，建议开启新对话以获得最佳体验！')
        } else if (percentage >= 75) {
            // 75%以上：明确提醒
            this.showTokenWarning('warning', '即将达到对话长度限制，请考虑开启新对话。')
        } else if (percentage >= 50) {
            // 50%以上：温和提示
            this.showTokenWarning('info', '对话较长，建议适时总结关键信息。')
        }
    }
    
    showTokenWarning(level, message) {
        // 避免重复显示相同级别的警告
        const existingWarning = document.querySelector(`.token-warning-${level}`)
        if (existingWarning) return
        
        // 创建警告消息
        this.addMessage('system', `⚠️ ${message}`, true, level)
    }
    
    optimizeHistory() {
        // 实现滑动窗口：只保留最近的对话
        if (this.searchHistory.length > this.tokenLimits.window * 2) {
            // 保留最近8轮对话（16条消息：8个用户+8个助手）
            const recentHistory = this.searchHistory.slice(-this.tokenLimits.window * 2)
            
            // 添加压缩提示
            const summaryMessage = {
                role: "system",
                content: "📝 为优化性能，已压缩早期对话内容。当前保留最近8轮对话上下文。"
            }
            
            this.searchHistory = [summaryMessage, ...recentHistory]
            
            // 保存优化后的历史
            this.saveChatHistory()
            
            console.log(`历史对话已优化：压缩前${this.searchHistory.length + (this.searchHistory.length - recentHistory.length - 1)}条，压缩后${this.searchHistory.length}条`)
        }
    }
    
    startNewConversation() {
        if (confirm('确定要开启新对话吗？当前对话将被保存到历史记录中。')) {
            // 保存当前对话到历史记录
            this.saveConversationToHistory()
            
            // 清空当前对话
            this.searchHistory = []
            this.currentTokenCount = 0
            this.chatMessages.innerHTML = `
                <div class="welcome-message">
                    <div class="welcome-icon">📚</div>
                    <h2>开启新对话</h2>
                    <p>已为您开启全新的对话会话</p>
                </div>
            `
            
            // 清空当前存储
            this.clearChatHistory()
            this.updateTokenDisplay()
            
            console.log('新对话已开启')
        }
    }
    
    saveConversationToHistory() {
        const timestamp = new Date().toISOString()
        const conversationKey = `conversation_${Date.now()}`
        
        try {
            const conversationData = {
                messages: this.getChatMessages(),
                searchHistory: this.searchHistory,
                timestamp: timestamp,
                tokenCount: this.currentTokenCount
            }
            
            localStorage.setItem(conversationKey, JSON.stringify(conversationData))
            console.log(`对话已保存到历史记录: ${conversationKey}`)
        } catch (error) {
            console.error('保存对话历史失败:', error)
        }
    }
    
    // 历史记录管理相关方法
    bindModalEvents() {
        // 关闭模态框事件
        document.getElementById('closeHistoryModal').addEventListener('click', () => this.closeModals())
        document.getElementById('closeConversationModal').addEventListener('click', () => this.closeModals())
        this.modalBackdrop.addEventListener('click', () => this.closeModals())
        
        // 历史记录搜索和排序
        this.historySearch.addEventListener('input', () => this.filterHistoryList())
        this.sortOrder.addEventListener('change', () => this.filterHistoryList())
        
        // 批量操作按钮
        document.getElementById('exportAllBtn').addEventListener('click', () => this.exportAllConversations())
        document.getElementById('deleteAllBtn').addEventListener('click', () => this.deleteAllHistory())
        
        // 对话详情操作按钮
        document.getElementById('restoreConversationBtn').addEventListener('click', () => this.restoreCurrentConversation())
        document.getElementById('exportConversationBtn').addEventListener('click', () => this.exportCurrentConversation())
        document.getElementById('deleteConversationBtn').addEventListener('click', () => this.deleteCurrentConversation())
        
        // ESC键关闭模态框
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModals()
            }
        })
    }
    
    openHistoryModal() {
        this.loadHistoryList()
        this.showModal(this.historyModal)
    }
    
    showModal(modal) {
        this.modalBackdrop.classList.remove('hidden')
        modal.classList.remove('hidden')
        document.body.style.overflow = 'hidden'
    }
    
    closeModals() {
        this.modalBackdrop.classList.add('hidden')
        this.historyModal.classList.add('hidden')
        this.conversationModal.classList.add('hidden')
        document.body.style.overflow = ''
        this.currentConversationKey = null
    }
    
    loadHistoryList() {
        const conversations = this.getAllConversations()
        this.updateHistoryStats(conversations)
        this.renderHistoryList(conversations)
    }
    
    getAllConversations() {
        const conversations = []
        
        // 遍历localStorage获取所有对话记录
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i)
            if (key && key.startsWith('conversation_')) {
                try {
                    const data = JSON.parse(localStorage.getItem(key))
                    conversations.push({
                        key: key,
                        timestamp: data.timestamp,
                        messages: data.messages || [],
                        searchHistory: data.searchHistory || [],
                        tokenCount: data.tokenCount || 0
                    })
                } catch (error) {
                    console.error(`解析对话记录失败: ${key}`, error)
                }
            }
        }
        
        return conversations
    }
    
    updateHistoryStats(conversations) {
        const totalConversations = conversations.length
        const totalMessages = conversations.reduce((sum, conv) => sum + conv.messages.length, 0)
        const totalTokens = conversations.reduce((sum, conv) => sum + (conv.tokenCount || 0), 0)
        
        this.historyStats.innerHTML = `
            <span>总对话数: <strong>${totalConversations}</strong></span>
            <span>总消息数: <strong>${totalMessages}</strong></span>
            <span>总Token数: <strong>${totalTokens.toLocaleString()}</strong></span>
        `
    }
    
    renderHistoryList(conversations) {
        if (conversations.length === 0) {
            this.historyList.innerHTML = `
                <div class="history-empty">
                    <p>📭 暂无历史对话记录</p>
                    <p>开始一段对话后，历史记录将在这里显示</p>
                </div>
            `
            return
        }
        
        this.historyList.innerHTML = conversations.map(conv => this.createHistoryItem(conv)).join('')
        
        // 绑定历史项点击事件
        this.historyList.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.classList.contains('history-item-btn')) {
                    const conversationKey = item.dataset.key
                    this.openConversationDetail(conversationKey)
                }
            })
        })
        
        // 绑定快捷操作按钮
        this.historyList.querySelectorAll('.history-item-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation()
                const conversationKey = btn.closest('.history-item').dataset.key
                const action = btn.dataset.action
                
                if (action === 'restore') {
                    this.restoreConversation(conversationKey)
                } else if (action === 'delete') {
                    this.deleteConversation(conversationKey)
                }
            })
        })
    }
    
    createHistoryItem(conversation) {
        const date = new Date(conversation.timestamp)
        const dateStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
        
        // 获取对话标题（第一条用户消息的内容）
        const firstUserMessage = conversation.messages.find(msg => msg.role === 'user')
        const title = firstUserMessage ? 
            (firstUserMessage.content.length > 50 ? 
             firstUserMessage.content.substring(0, 50) + '...' : 
             firstUserMessage.content) : 
            '未知对话'
        
        // 获取对话预览（最后几条消息）
        const recentMessages = conversation.messages.slice(-2)
        const preview = recentMessages.map(msg => {
            const roleText = msg.role === 'user' ? '用户' : msg.role === 'assistant' ? '助手' : '系统'
            const content = msg.content.length > 100 ? msg.content.substring(0, 100) + '...' : msg.content
            return `${roleText}: ${content}`
        }).join('\\n')
        
        return `
            <div class="history-item" data-key="${conversation.key}">
                <div class="history-item-header">
                    <div class="history-item-title">${title}</div>
                    <div class="history-item-date">${dateStr}</div>
                </div>
                <div class="history-item-preview">${preview}</div>
                <div class="history-item-meta">
                    <div class="history-item-stats">
                        <span>消息数: ${conversation.messages.length}</span>
                        <span>Token数: ${(conversation.tokenCount || 0).toLocaleString()}</span>
                    </div>
                    <div class="history-item-actions">
                        <button class="history-item-btn restore" data-action="restore">恢复</button>
                        <button class="history-item-btn delete" data-action="delete">删除</button>
                    </div>
                </div>
            </div>
        `
    }
    
    filterHistoryList() {
        const searchTerm = this.historySearch.value.toLowerCase()
        const sortOrder = this.sortOrder.value
        
        let conversations = this.getAllConversations()
        
        // 搜索过滤
        if (searchTerm) {
            conversations = conversations.filter(conv => {
                const searchContent = conv.messages
                    .map(msg => msg.content.toLowerCase())
                    .join(' ')
                return searchContent.includes(searchTerm)
            })
        }
        
        // 排序
        conversations.sort((a, b) => {
            switch (sortOrder) {
                case 'newest':
                    return new Date(b.timestamp) - new Date(a.timestamp)
                case 'oldest':
                    return new Date(a.timestamp) - new Date(b.timestamp)
                case 'longest':
                    return b.messages.length - a.messages.length
                case 'shortest':
                    return a.messages.length - b.messages.length
                default:
                    return new Date(b.timestamp) - new Date(a.timestamp)
            }
        })
        
        this.updateHistoryStats(conversations)
        this.renderHistoryList(conversations)
    }
    
    openConversationDetail(conversationKey) {
        try {
            const conversationData = JSON.parse(localStorage.getItem(conversationKey))
            if (!conversationData) return
            
            this.currentConversationKey = conversationKey
            
            // 设置标题
            const firstUserMessage = conversationData.messages.find(msg => msg.role === 'user')
            const title = firstUserMessage ? 
                (firstUserMessage.content.length > 30 ? 
                 firstUserMessage.content.substring(0, 30) + '...' : 
                 firstUserMessage.content) : 
                '未知对话'
            document.getElementById('conversationTitle').textContent = title
            
            // 显示统计信息
            const date = new Date(conversationData.timestamp)
            document.getElementById('conversationInfo').innerHTML = `
                <div class="conversation-stat">
                    <span class="conversation-stat-value">${conversationData.messages.length}</span>
                    <span class="conversation-stat-label">消息数量</span>
                </div>
                <div class="conversation-stat">
                    <span class="conversation-stat-value">${(conversationData.tokenCount || 0).toLocaleString()}</span>
                    <span class="conversation-stat-label">Token数量</span>
                </div>
                <div class="conversation-stat">
                    <span class="conversation-stat-value">${date.toLocaleDateString()}</span>
                    <span class="conversation-stat-label">创建日期</span>
                </div>
                <div class="conversation-stat">
                    <span class="conversation-stat-value">${date.toLocaleTimeString()}</span>
                    <span class="conversation-stat-label">创建时间</span>
                </div>
            `
            
            // 显示对话内容
            document.getElementById('conversationContent').innerHTML = 
                conversationData.messages.map(msg => this.createConversationMessage(msg)).join('')
            
            // 显示对话详情模态框
            this.showModal(this.conversationModal)
            
        } catch (error) {
            console.error('打开对话详情失败:', error)
            alert('无法打开对话详情，数据可能已损坏')
        }
    }
    
    createConversationMessage(message) {
        const avatar = message.role === 'user' ? '👤' : message.role === 'assistant' ? '🤖' : '⚠️'
        return `
            <div class="conversation-message ${message.role}">
                <div class="conversation-avatar">${avatar}</div>
                <div class="conversation-message-content">${message.content}</div>
            </div>
        `
    }
    
    restoreConversation(conversationKey) {
        if (confirm('确定要恢复这段对话吗？当前对话将被替换。')) {
            try {
                const conversationData = JSON.parse(localStorage.getItem(conversationKey))
                if (conversationData) {
                    // 恢复对话数据
                    this.searchHistory = conversationData.searchHistory || []
                    
                    // 清空当前界面
                    this.chatMessages.innerHTML = ''
                    
                    // 恢复消息显示
                    conversationData.messages.forEach(msg => {
                        this.addMessageToDOM(msg.role, msg.content, msg.timestamp, false)
                    })
                    
                    // 更新存储和显示
                    this.saveChatHistory()
                    this.updateTokenDisplay()
                    this.scrollToBottom()
                    
                    // 关闭模态框
                    this.closeModals()
                    
                    console.log('对话已恢复:', conversationKey)
                }
            } catch (error) {
                console.error('恢复对话失败:', error)
                alert('恢复对话失败，数据可能已损坏')
            }
        }
    }
    
    restoreCurrentConversation() {
        if (this.currentConversationKey) {
            this.restoreConversation(this.currentConversationKey)
        }
    }
    
    deleteConversation(conversationKey) {
        if (confirm('确定要删除这段对话吗？此操作无法撤销。')) {
            localStorage.removeItem(conversationKey)
            this.loadHistoryList()  // 刷新历史列表
            console.log('对话已删除:', conversationKey)
        }
    }
    
    deleteCurrentConversation() {
        if (this.currentConversationKey) {
            this.deleteConversation(this.currentConversationKey)
            this.closeModals()
        }
    }
    
    deleteAllHistory() {
        if (confirm('确定要清空所有历史记录吗？此操作无法撤销。')) {
            // 删除所有conversation_开头的键
            const keysToDelete = []
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i)
                if (key && key.startsWith('conversation_')) {
                    keysToDelete.push(key)
                }
            }
            
            keysToDelete.forEach(key => localStorage.removeItem(key))
            this.loadHistoryList()  // 刷新列表
            
            console.log(`已删除${keysToDelete.length}个历史对话记录`)
        }
    }
    
    exportCurrentConversation() {
        if (this.currentConversationKey) {
            this.exportConversation(this.currentConversationKey)
        }
    }
    
    exportConversation(conversationKey) {
        try {
            const conversationData = JSON.parse(localStorage.getItem(conversationKey))
            if (!conversationData) return
            
            // 创建导出内容
            const exportContent = this.formatConversationForExport(conversationData)
            
            // 创建文件并下载
            const blob = new Blob([exportContent], { type: 'text/plain;charset=utf-8' })
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            
            const date = new Date(conversationData.timestamp).toISOString().split('T')[0]
            const firstMessage = conversationData.messages.find(msg => msg.role === 'user')
            const title = firstMessage ? firstMessage.content.substring(0, 20) : '对话记录'
            
            a.href = url
            a.download = `对话记录_${title}_${date}.txt`
            a.click()
            
            URL.revokeObjectURL(url)
            console.log('对话已导出:', conversationKey)
            
        } catch (error) {
            console.error('导出对话失败:', error)
            alert('导出对话失败')
        }
    }
    
    exportAllConversations() {
        const conversations = this.getAllConversations()
        if (conversations.length === 0) {
            alert('没有可导出的对话记录')
            return
        }
        
        if (confirm(`确定要导出全部${conversations.length}个对话记录吗？`)) {
            try {
                // 按时间排序
                conversations.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
                
                // 创建导出内容
                let exportContent = '# 聊天记录导出\\n\\n'
                exportContent += `导出时间: ${new Date().toISOString()}\\n`
                exportContent += `总对话数: ${conversations.length}\\n\\n`
                
                conversations.forEach((conv, index) => {
                    exportContent += `## 对话 ${index + 1}\\n\\n`
                    exportContent += this.formatConversationForExport(conv)
                    exportContent += '\\n' + '='.repeat(50) + '\\n\\n'
                })
                
                // 创建文件并下载
                const blob = new Blob([exportContent], { type: 'text/plain;charset=utf-8' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                
                const date = new Date().toISOString().split('T')[0]
                a.href = url
                a.download = `全部聊天记录_${date}.txt`
                a.click()
                
                URL.revokeObjectURL(url)
                console.log('全部对话已导出')
                
            } catch (error) {
                console.error('导出全部对话失败:', error)
                alert('导出失败')
            }
        }
    }
    
    formatConversationForExport(conversationData) {
        const date = new Date(conversationData.timestamp)
        let content = `创建时间: ${date.toLocaleString()}\\n`
        content += `消息数量: ${conversationData.messages.length}\\n`
        content += `Token数量: ${conversationData.tokenCount || 0}\\n\\n`
        
        conversationData.messages.forEach((msg, index) => {
            const roleText = msg.role === 'user' ? '用户' : msg.role === 'assistant' ? '助手' : '系统'
            content += `[${index + 1}] ${roleText}: ${msg.content}\\n\\n`
        })
        
        return content
    }
    
    // 移除所有动画相关方法，保持代码简洁
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    new PaperSearchApp()
})