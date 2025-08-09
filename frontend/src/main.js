import './style.css'
import { ChatAPI } from './api.js'

class PaperSearchApp {
    constructor() {
        this.searchAPI = new ChatAPI()
        this.searchHistory = []
        this.isLoading = false
        this.storageKey = 'paper_search_chat_history'
        
        this.initElements()
        this.bindEvents()
        this.loadChatHistory()
        this.checkAPIHealth()
    }
    
    initElements() {
        this.chatMessages = document.getElementById('chatMessages')
        this.messageInput = document.getElementById('messageInput')
        this.sendBtn = document.getElementById('sendBtn')
        this.clearBtn = document.getElementById('clearBtn')
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
            // 调用搜索API
            const response = await this.searchAPI.sendMessage(message, this.searchHistory)
            
            // 添加搜索结果
            this.addMessage('assistant', response.response)
            
            // 更新搜索历史
            this.searchHistory = response.history
            
        } catch (error) {
            console.error('发送消息失败:', error)
            this.addMessage('system', '抱歉，搜索论文时出现错误。请稍后再试。')
        } finally {
            this.isLoading = false
            this.sendBtn.disabled = this.messageInput.value.trim().length === 0
            this.messageInput.disabled = false
        }
    }
    
    addMessage(role, content) {
        // 移除欢迎消息
        const welcomeMessage = this.chatMessages.querySelector('.welcome-message')
        if (welcomeMessage) {
            welcomeMessage.remove()
        }
        
        // 添加消息到DOM
        this.addMessageToDOM(role, content)
        
        // 保存到localStorage
        this.saveChatHistory()
        
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
    
    addMessageToDOM(role, content, timestamp = null, useTyping = true) {
        const messageDiv = document.createElement('div')
        messageDiv.className = `message ${role}-message`
        
        const avatar = document.createElement('div')
        avatar.className = 'message-avatar'
        avatar.textContent = role === 'user' ? '👤' : role === 'assistant' ? '🤖' : '⚠️'
        
        const content_div = document.createElement('div')
        content_div.className = 'message-content'
        
        const timestampDiv = document.createElement('div')
        timestampDiv.className = 'message-timestamp'
        timestampDiv.textContent = timestamp || new Date().toLocaleTimeString()
        
        messageDiv.appendChild(avatar)
        messageDiv.appendChild(content_div)
        messageDiv.appendChild(timestampDiv)
        
        this.chatMessages.appendChild(messageDiv)
        
        // 对助手消息使用打字机效果（仅在useTyping为true时）
        if (role === 'assistant' && useTyping) {
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
    
    // 移除所有动画相关方法，保持代码简洁
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    new PaperSearchApp()
})