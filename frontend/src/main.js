import './style.css'
import { ChatAPI } from './api.js'

class PaperSearchApp {
    constructor() {
        this.searchAPI = new ChatAPI()
        this.searchHistory = []
        this.isLoading = false
        
        this.initElements()
        this.bindEvents()
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
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            this.sendMessage()
        }
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
        
        const messageDiv = document.createElement('div')
        messageDiv.className = `message ${role}-message`
        
        const avatar = document.createElement('div')
        avatar.className = 'message-avatar'
        avatar.textContent = role === 'user' ? '👤' : role === 'assistant' ? '🤖' : '⚠️'
        
        const content_div = document.createElement('div')
        content_div.className = 'message-content'
        content_div.textContent = content
        
        const timestamp = document.createElement('div')
        timestamp.className = 'message-timestamp'
        timestamp.textContent = new Date().toLocaleTimeString()
        
        messageDiv.appendChild(avatar)
        messageDiv.appendChild(content_div)
        messageDiv.appendChild(timestamp)
        
        this.chatMessages.appendChild(messageDiv)
        
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
    
    // 移除所有动画相关方法，保持代码简洁
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    new PaperSearchApp()
})