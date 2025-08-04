/**
 * API通信模块
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? '/api' : 'http://localhost:8000')

export class ChatAPI {
    constructor() {
        this.baseURL = API_BASE_URL
    }
    
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        }
        
        try {
            const response = await fetch(url, config)
            
            if (!response.ok) {
                throw new Error(`HTTP错误! 状态: ${response.status}`)
            }
            
            return await response.json()
        } catch (error) {
            console.error('API请求失败:', error)
            throw error
        }
    }
    
    async checkHealth() {
        return await this.request('/health')
    }
    
    async sendMessage(message, history = []) {
        const payload = {
            message: message,
            history: history.map(msg => ({
                role: msg.role,
                content: msg.content
            }))
        }
        
        return await this.request('/chat', {
            method: 'POST',
            body: JSON.stringify(payload)
        })
    }
    
    async getModels() {
        return await this.request('/models')
    }
}