import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { api } from './config';
import KeywordCloudWidget from './components/KeywordCloudWidget';
import TokenProgress from './components/TokenProgress';
import { 
  UnifiedHistoryService,
  type HistoryItem, 
  type SearchHistory, 
  type ChatHistory 
} from './services/dataService';

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: number;
  analysisResult?: any;
  hierarchicalKeywords?: any;
}

interface ChatInterfaceProps {
  className?: string;
}

const CHAT_STORAGE_KEY = 'veritex_chat_history';
const CHAT_ANALYSIS_KEY = 'veritex_current_analysis';

const ChatInterface: React.FC<ChatInterfaceProps> = ({ className = '' }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentAnalysis, setCurrentAnalysis] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // 关键词云面板状态
  const [isKeywordPanelCollapsed, setIsKeywordPanelCollapsed] = useState(false);
  const [keywordPanelWidth, setKeywordPanelWidth] = useState(350);
  const [isResizing, setIsResizing] = useState(false);
  
  // My面板状态
  const [isMyPanelCollapsed, setIsMyPanelCollapsed] = useState(false);
  const [myPanelWidth] = useState(300);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  
  // My面板历史记录状态
  const [unifiedHistory, setUnifiedHistory] = useState<HistoryItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [filter, setFilter] = useState<'search' | 'chat'>('search');
  
  // 操作菜单状态
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>('');
  
  // LLM模式状态
  const [llmMode, setLlmMode] = useState<'auto-search' | 'chat-plan'>(() => {
    const saved = localStorage.getItem('veritex_llm_mode');
    return (saved as 'auto-search' | 'chat-plan') || 'auto-search';
  });
  
  // 从首页传来的初始输入
  const initialInput = location.state?.input || '';
  const preserveChat = location.state?.preserveChat || false;

  // 保存聊天记录到localStorage（会话级别）
  const saveChatHistory = (messages: Message[], analysis: any = null) => {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
    if (analysis) {
      localStorage.setItem(CHAT_ANALYSIS_KEY, JSON.stringify(analysis));
    }
    
    // 保存完整对话会话到统一历史记录
    saveChatSessionToHistory(messages);
  };
  
  // 会话级别的聊天记录保存（整个对话会话）
  const saveChatSessionToHistory = (messages: Message[]) => {
    if (messages.length <= 1) return; // 只有欢迎消息时不保存
    
    const userMessages = messages.filter(m => m.isUser);
    if (userMessages.length === 0) return;
    
    // 使用第一个用户消息作为标题，但检查是否有更有意义的学术查询
    const academicMessages = userMessages.filter(m => 
      m.text.includes('研究') || m.text.includes('论文') || m.text.includes('学术') ||
      m.text.includes('research') || m.text.includes('paper') || m.text.includes('study')
    );
    const representativeMessage = academicMessages.length > 0 ? academicMessages[0] : userMessages[0];
    
    const title = representativeMessage.text.slice(0, 50) + (representativeMessage.text.length > 50 ? '...' : '');
    const sessionId = 'chat_session_' + messages[0].timestamp; // 使用第一条消息时间戳作为会话ID
    
    const chatSession = {
      id: sessionId,
      timestamp: messages[0].timestamp,
      title: title,
      messages: messages,
      lastActivity: messages[messages.length - 1].timestamp,
      messageCount: userMessages.length,
      type: 'session'
    };
    
    try {
      const CHAT_STORAGE_KEY_UNIFIED = 'paper_god_chat_history';
      const UNIFIED_HISTORY_KEY = 'paper_god_unified_history';
      
      // 更新或创建聊天会话记录
      const existingChatHistory = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY_UNIFIED) || '[]');
      const existingIndex = existingChatHistory.findIndex((item: any) => item.id === sessionId);
      
      if (existingIndex >= 0) {
        existingChatHistory[existingIndex] = chatSession;
      } else {
        existingChatHistory.unshift(chatSession);
      }
      
      if (existingChatHistory.length > 50) {
        existingChatHistory.splice(50);
      }
      localStorage.setItem(CHAT_STORAGE_KEY_UNIFIED, JSON.stringify(existingChatHistory));
      
      // 保存到统一历史
      const unifiedItem = {
        id: sessionId,
        timestamp: chatSession.lastActivity,
        type: 'chat' as const,
        title: title,
        data: chatSession
      };
      
      const existingUnifiedHistory = JSON.parse(localStorage.getItem(UNIFIED_HISTORY_KEY) || '[]');
      const unifiedIndex = existingUnifiedHistory.findIndex((h: any) => h.id === sessionId);
      
      if (unifiedIndex >= 0) {
        existingUnifiedHistory[unifiedIndex] = unifiedItem;
      } else {
        existingUnifiedHistory.unshift(unifiedItem);
      }
      
      existingUnifiedHistory.sort((a: any, b: any) => b.timestamp - a.timestamp);
      
      if (existingUnifiedHistory.length > 100) {
        existingUnifiedHistory.splice(100);
      }
      localStorage.setItem(UNIFIED_HISTORY_KEY, JSON.stringify(existingUnifiedHistory));
      
    } catch (error) {
      console.error('Error saving chat session to history:', error);
    }
  };

  // 保存学术搜索结果到Search历史
  const saveSearchResultToHistory = (userQuery: string, response: any) => {
    if (!response.is_academic_query || !response.search_results || response.search_results.length === 0) {
      return;
    }

    const searchId = 'search_' + Date.now();
    const searchHistory = {
      id: searchId,
      timestamp: Date.now(),
      originalQuery: userQuery,
      expandedKeywords: response.analysis_result?.hierarchical_keywords ? 
        Object.values(response.analysis_result.hierarchical_keywords).flatMap((level: any) => level.terms || []) : [],
      papers: response.search_results,
      maxResults: response.search_results.length,
      domain: response.analysis_result?.domain || 'unknown'
    };

    try {
      const SEARCH_STORAGE_KEY = 'paper_god_search_history';
      const UNIFIED_HISTORY_KEY = 'paper_god_unified_history';
      
      // 保存到搜索历史
      const existingSearchHistory = JSON.parse(localStorage.getItem(SEARCH_STORAGE_KEY) || '[]');
      existingSearchHistory.unshift(searchHistory);
      
      if (existingSearchHistory.length > 50) {
        existingSearchHistory.splice(50);
      }
      localStorage.setItem(SEARCH_STORAGE_KEY, JSON.stringify(existingSearchHistory));
      
      // 保存到统一历史
      // 使用Exact Terms作为Search results的标题
      const exactTerms = response.analysis_result?.exact_terms || userQuery;
      const unifiedItem = {
        id: searchId,
        timestamp: searchHistory.timestamp,
        type: 'search' as const,
        title: exactTerms.length > 50 ? exactTerms.slice(0, 50) + '...' : exactTerms,
        data: searchHistory
      };
      
      const existingUnifiedHistory = JSON.parse(localStorage.getItem(UNIFIED_HISTORY_KEY) || '[]');
      existingUnifiedHistory.unshift(unifiedItem);
      
      existingUnifiedHistory.sort((a: any, b: any) => b.timestamp - a.timestamp);
      
      if (existingUnifiedHistory.length > 100) {
        existingUnifiedHistory.splice(100);
      }
      localStorage.setItem(UNIFIED_HISTORY_KEY, JSON.stringify(existingUnifiedHistory));
      
    } catch (error) {
      console.error('Error saving search result to history:', error);
    }
  };

  // 从localStorage恢复聊天记录
  const loadChatHistory = (): { messages: Message[], analysis: any } => {
    try {
      const savedMessages = localStorage.getItem(CHAT_STORAGE_KEY);
      const savedAnalysis = localStorage.getItem(CHAT_ANALYSIS_KEY);
      return {
        messages: savedMessages ? JSON.parse(savedMessages) : [],
        analysis: savedAnalysis ? JSON.parse(savedAnalysis) : null
      };
    } catch (error) {
      console.error('Error loading chat history:', error);
      return { messages: [], analysis: null };
    }
  };

  // 清除聊天历史

  // 初始化聊天记录
  useEffect(() => {
    const { messages: savedMessages, analysis: savedAnalysis } = loadChatHistory();
    
    // 如果有保存的聊天记录，恢复它们
    if (savedMessages.length > 0) {
      setMessages(savedMessages);
      setCurrentAnalysis(savedAnalysis);
    } else {
      // 否则显示欢迎消息
      const welcomeMessage: Message = {
        id: 'welcome',
        text: '👋 您好！我是Veritex智能助手。您可以：\n\n📚 发送学术查询，我会为您分析并扩展关键词\n🔍 直接搜索文献\n💬 与我对话交流学术问题\n\n请输入您的问题或研究主题吧！',
        isUser: false,
        timestamp: Date.now()
      };
      const initialMessages = [welcomeMessage];
      setMessages(initialMessages);
      saveChatHistory(initialMessages);
    }
    
    // 如果有来自首页的初始输入，设置到输入框中
    if (initialInput && !preserveChat) {
      // 只有在不保留聊天记录的情况下才设置初始输入
      setInputMessage(initialInput);
    } else if (initialInput && preserveChat) {
      // 如果需要保留聊天记录且有新输入，直接设置到输入框
      setInputMessage(initialInput);
    }
  }, [initialInput, preserveChat]);

  // 加载My面板历史记录
  const loadMyPanelHistory = async () => {
    const userId = localStorage.getItem('user_id');
    if (!userId) {
      setUnifiedHistory([]);
      return;
    }
    try {
      const history = await UnifiedHistoryService.getHistory(userId);
      setUnifiedHistory(history);
    } catch (error) {
      console.error('Error loading history:', error);
      setUnifiedHistory([]);
    }
  };

  // 每次展开My面板时刷新历史记录
  useEffect(() => {
    if (!isMyPanelCollapsed) {
      loadMyPanelHistory();
    }
  }, [isMyPanelCollapsed]);

  // 处理窗口大小变化
  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth <= 768;
      setIsMobile(mobile);
      // 移动端默认折叠My面板
      if (mobile && !isMyPanelCollapsed) {
        // 移动端展开时保持展开状态，但监听点击关闭
      }
    };
    
    window.addEventListener('resize', handleResize);
    handleResize();
    
    return () => window.removeEventListener('resize', handleResize);
  }, [isMyPanelCollapsed]);

  // My面板相关函数
  const filteredHistory = unifiedHistory.filter(item => item.type === filter);

  const handleSelectAll = () => {
    if (selectAll) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filteredHistory.map(item => item.id));
    }
    setSelectAll(!selectAll);
  };

  const handleSelectItem = (id: string) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter(sid => sid !== id));
    } else {
      setSelectedIds([...selectedIds, id]);
    }
  };

  const handleDeleteSelected = async () => {
    if (selectedIds.length === 0) return;
    
    if (confirm(`确定要删除选中的 ${selectedIds.length} 条记录吗？`)) {
      const userId = localStorage.getItem('user_id');
      if (userId) {
        try {
          await UnifiedHistoryService.deleteHistory(userId, selectedIds);
          setSelectedIds([]);
          setSelectAll(false);
          await loadMyPanelHistory();
        } catch (error) {
          console.error('Delete failed:', error);
        }
      }
    }
  };

  const handleClearAll = async () => {
    if (confirm('确定要清空所有历史记录吗？此操作不可恢复。')) {
      const userId = localStorage.getItem('user_id');
      if (userId) {
        try {
          await UnifiedHistoryService.clearAll(userId);
          setUnifiedHistory([]);
          setSelectedIds([]);
          setSelectAll(false);
        } catch (error) {
          console.error('Clear all failed:', error);
        }
      }
    }
  };

  const handleViewItem = (item: HistoryItem) => {
    if (item.type === 'search') {
      const searchData = item.data as SearchHistory;
      navigate('/report', {
        state: {
          papers: searchData.papers,
          searchHistory: searchData,
          expandedKeywords: searchData.expandedKeywords,
          originalQuery: searchData.originalQuery,
          maxResults: searchData.maxResults
        }
      });
    } else if (item.type === 'chat') {
      const chatData = item.data as ChatHistory;
      localStorage.setItem('veritex_chat_history', JSON.stringify(chatData.messages));
      window.location.reload();
    }
  };

  // 置顶功能
  const handlePinItem = async (itemId: string) => {
    try {
      const userId = localStorage.getItem('paper_god_user_id') || 'anonymous';
      const currentHistory = await UnifiedHistoryService.getHistory(userId);
      
      // 找到要置顶的项目
      const itemToPin = currentHistory.find(item => item.id === itemId);
      if (!itemToPin) return;
      
      // 更新时间戳为当前时间，实现置顶效果
      const updatedItem = { ...itemToPin, timestamp: Date.now() };
      
      // 更新本地存储
      const UNIFIED_HISTORY_KEY = 'paper_god_unified_history';
      const existingHistory = JSON.parse(localStorage.getItem(UNIFIED_HISTORY_KEY) || '[]');
      const updatedHistory = existingHistory.map((h: any) => 
        h.id === itemId ? updatedItem : h
      ).sort((a: any, b: any) => b.timestamp - a.timestamp);
      
      localStorage.setItem(UNIFIED_HISTORY_KEY, JSON.stringify(updatedHistory));
      
      // 重新加载历史记录
      loadMyPanelHistory();
      setActiveMenuId(null);
    } catch (error) {
      console.error('Pin item failed:', error);
    }
  };

  // 重命名功能
  const handleRenameItem = async (itemId: string, newTitle: string) => {
    try {
      
      // 更新本地存储中的标题
      const UNIFIED_HISTORY_KEY = 'paper_god_unified_history';
      const existingHistory = JSON.parse(localStorage.getItem(UNIFIED_HISTORY_KEY) || '[]');
      const updatedHistory = existingHistory.map((h: any) => 
        h.id === itemId ? { ...h, title: newTitle } : h
      );
      
      localStorage.setItem(UNIFIED_HISTORY_KEY, JSON.stringify(updatedHistory));
      
      // 同时更新对应的具体历史记录
      if (itemId.startsWith('search_')) {
        const SEARCH_STORAGE_KEY = 'paper_god_search_history';
        const searchHistory = JSON.parse(localStorage.getItem(SEARCH_STORAGE_KEY) || '[]');
        const updatedSearchHistory = searchHistory.map((s: any) => 
          s.id === itemId ? { ...s, customTitle: newTitle } : s
        );
        localStorage.setItem(SEARCH_STORAGE_KEY, JSON.stringify(updatedSearchHistory));
      } else if (itemId.startsWith('chat_')) {
        const CHAT_STORAGE_KEY = 'paper_god_chat_history';
        const chatHistory = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || '[]');
        const updatedChatHistory = chatHistory.map((c: any) => 
          c.id === itemId ? { ...c, title: newTitle } : c
        );
        localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(updatedChatHistory));
      }
      
      // 重新加载历史记录
      loadMyPanelHistory();
      setEditingId(null);
      setEditingTitle('');
      setActiveMenuId(null);
    } catch (error) {
      console.error('Rename item failed:', error);
    }
  };

  // 开始重命名
  const startRenaming = (item: HistoryItem) => {
    setEditingId(item.id);
    setEditingTitle(item.title);
    setActiveMenuId(null);
  };

  // 点击外部关闭菜单
  useEffect(() => {
    const handleClickOutside = () => {
      if (activeMenuId) {
        setActiveMenuId(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [activeMenuId]);


  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 处理拖拽调整宽度
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      
      const newWidth = window.innerWidth - e.clientX;
      const minWidth = 280;
      const maxWidth = window.innerWidth * 0.6;
      
      setKeywordPanelWidth(Math.min(Math.max(newWidth, minWidth), maxWidth));
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);

  // 检查登录状态
  useEffect(() => {
    const isLoggedIn = localStorage.getItem('invite_logged_in') === '1';
    const userId = localStorage.getItem('user_id');
    
    if (!isLoggedIn || !userId) {
      localStorage.removeItem('invite_logged_in');
      localStorage.removeItem('user_id');
      navigate('/invite');
    }
  }, [navigate]);

  // 发送消息
  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputMessage.trim(),
      isUser: true,
      timestamp: Date.now()
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    saveChatHistory(newMessages, currentAnalysis);
    setInputMessage('');
    setIsLoading(true);

    try {
      // 调用后端chat API
      const response = await api.chat(userMessage.text, []);
      
      // 检查是否是学术查询（有搜索结果）
      let analysisResult = null;
      let hierarchicalKeywords = null;
      
      // 尝试从多个来源提取分析结果和关键词
      if (response.analysis_result) {
        analysisResult = response.analysis_result;
        
        // 尝试从分析结果中提取层次化关键词
        if (analysisResult && analysisResult.hierarchical_keywords) {
          hierarchicalKeywords = analysisResult.hierarchical_keywords;
          setCurrentAnalysis(analysisResult);
        }
      }
      
      // 如果没有hierarchical_keywords，尝试从响应文本中提取关键词
      if (!hierarchicalKeywords && response.is_academic_query && response.response) {
        const keywordsMatch = response.response.match(/🏷️\s*\*\*关键词\*\*:\s*([^\n]+)/);
        if (keywordsMatch) {
          const keywordsText = keywordsMatch[1];
          const keywords = keywordsText.split(/[,，]\s*/).map((k: string) => k.trim()).filter((k: string) => k);
          
          // 创建简化的hierarchical_keywords结构
          hierarchicalKeywords = {
            core_synonyms: {
              terms: keywords,
              weight: 1.0
            }
          };
          
          // 创建分析结果
          analysisResult = {
            hierarchical_keywords: hierarchicalKeywords,
            domain: 'academic_research'
          };
          
          setCurrentAnalysis(analysisResult);
        }
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.response || '抱歉，我无法处理您的请求。',
        isUser: false,
        timestamp: Date.now() + 1,
        analysisResult,
        hierarchicalKeywords
      };

      const finalMessages = [...newMessages, assistantMessage];
      setMessages(finalMessages);
      saveChatHistory(finalMessages, analysisResult);

      // 如果是学术查询并有搜索结果，保存到Search历史
      if (response.is_academic_query && response.search_results && response.search_results.length > 0) {
        saveSearchResultToHistory(userMessage.text, response);
      }

    } catch (error: any) {
      console.error('Chat error:', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: `抱歉，发生了错误：${error.message || '未知错误'}`,
        isUser: false,
        timestamp: Date.now() + 1
      };
      const errorMessages = [...newMessages, errorMessage];
      setMessages(errorMessages);
      saveChatHistory(errorMessages, currentAnalysis);
    } finally {
      setIsLoading(false);
    }
  };


  // 处理键盘事件
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // 格式化时间
  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  return (
    <div className={`chat-interface ${className}`} style={{
      display: 'flex',
      height: '100vh',
      backgroundColor: '#000',
      color: '#fff',
      overflow: 'hidden'
    }}>
      {/* 左侧My面板 */}
      {!isMyPanelCollapsed && (
        <div style={{
          width: isMobile ? '100vw' : `${myPanelWidth}px`,
          height: '100vh',
          borderRight: '1px solid #333',
          backgroundColor: '#0a0a0a',
          display: 'flex',
          flexDirection: 'column',
          minWidth: isMobile ? '100vw' : '280px',
          position: isMobile ? 'fixed' : 'relative',
          top: isMobile ? '0' : 'auto',
          left: isMobile ? '0' : 'auto',
          zIndex: isMobile ? 1000 : 'auto'
        }}>
          {/* My面板头部 */}
          <div style={{
            padding: '12px 16px',
            borderBottom: '1px solid #333',
            backgroundColor: '#111'
          }}>
            {/* Recent标题和New search按钮 */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '12px'
            }}>
              <h3 style={{ 
                margin: '0', 
                fontSize: '14px', 
                fontWeight: '600',
                color: '#fff'
              }}>
                Recent
              </h3>
              
              {/* New search按钮 */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <button
                  onClick={() => {
                    // 清除当前聊天并开始新的搜索
                    localStorage.removeItem(CHAT_STORAGE_KEY);
                    localStorage.removeItem(CHAT_ANALYSIS_KEY);
                    const welcomeMessage: Message = {
                      id: 'welcome',
                      text: '👋 您好！我是Veritex智能助手。您可以：\n\n📚 发送学术查询，我会为您分析并扩展关键词\n🔍 直接搜索文献\n💬 与我对话交流学术问题\n\n请输入您的问题或研究主题吧！',
                      isUser: false,
                      timestamp: Date.now()
                    };
                    const resetMessages = [welcomeMessage];
                    setMessages(resetMessages);
                    setCurrentAnalysis(null);
                    saveChatHistory(resetMessages);
                  }}
                  style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    border: '1px solid #10b981',
                    backgroundColor: 'rgba(16,185,129,0.1)',
                    color: '#10b981',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '12px',
                    fontWeight: '600'
                  }}
                  title="开始新的搜索对话"
                >
                  +
                </button>
                <span style={{
                  fontSize: '12px',
                  color: '#999',
                  fontWeight: '500'
                }}>
                  New search
                </span>
              </div>
            </div>
            
            {/* 移动端关闭按钮 */}
            {isMobile && (
              <button
                onClick={() => setIsMyPanelCollapsed(true)}
                style={{
                  position: 'absolute',
                  top: '12px',
                  right: '12px',
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  border: '1px solid #666',
                  background: 'rgba(0,0,0,0.8)',
                  color: '#999',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '12px',
                  zIndex: 1001
                }}
              >
                ✕
              </button>
            )}
            
            {/* 筛选器 */}
            <div style={{
              display: 'flex',
              gap: '4px',
              marginBottom: '8px'
            }}>
              <button
                onClick={() => setFilter('search')}
                style={{
                  flex: 1,
                  padding: '6px 12px',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '12px',
                  cursor: 'pointer',
                  backgroundColor: filter === 'search' ? '#3bb0e6' : '#333',
                  color: filter === 'search' ? '#fff' : '#999',
                  transition: 'all 0.2s'
                }}
              >
                Search results ({unifiedHistory.filter(h => h.type === 'search').length})
              </button>
              <button
                onClick={() => setFilter('chat')}
                style={{
                  flex: 1,
                  padding: '6px 12px',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '12px',
                  cursor: 'pointer',
                  backgroundColor: filter === 'chat' ? '#3bb0e6' : '#333',
                  color: filter === 'chat' ? '#fff' : '#999',
                  transition: 'all 0.2s'
                }}
              >
                Chat ({unifiedHistory.filter(h => h.type === 'chat').length})
              </button>
            </div>
            
            {/* 批量操作栏 */}
            {filteredHistory.length > 0 && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '12px'
              }}>
                <label style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  cursor: 'pointer',
                  color: '#999'
                }}>
                  <input
                    type="checkbox"
                    checked={selectAll}
                    onChange={handleSelectAll}
                    style={{
                      width: '12px',
                      height: '12px',
                      accentColor: '#3bb0e6'
                    }}
                  />
                  Select all
                </label>
                {selectedIds.length > 0 && (
                  <>
                    <span style={{ color: '#666' }}>|</span>
                    <button
                      onClick={handleDeleteSelected}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#ff6b6b',
                        cursor: 'pointer',
                        fontSize: '12px',
                        padding: '2px 4px'
                      }}
                    >
                      Delete({selectedIds.length})
                    </button>
                    <button
                      onClick={handleClearAll}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#ff6b6b',
                        cursor: 'pointer',
                        fontSize: '12px',
                        padding: '2px 4px'
                      }}
                    >
                      Clear all
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
          
          {/* My面板内容 */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '8px'
          }}>
            {filteredHistory.length === 0 ? (
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                color: '#666',
                textAlign: 'center'
              }}>
                <p style={{ margin: 0, fontSize: '12px' }}>
                  No {filter === 'search' ? 'search results' : 'chat'} history yet
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {filteredHistory.map((item) => (
                  <div
                    key={item.id}
                    onClick={(e) => {
                      // 如果点击的是复选框，不触发查看操作
                      if ((e.target as HTMLInputElement).type === 'checkbox') {
                        return;
                      }
                      handleViewItem(item);
                    }}
                    style={{
                      backgroundColor: selectedIds.includes(item.id) ? 'rgba(59,176,230,0.1)' : '#1a1a1a',
                      border: selectedIds.includes(item.id) ? '1px solid #3bb0e6' : '1px solid #333',
                      borderRadius: '6px',
                      padding: '8px',
                      cursor: 'pointer',
                      transition: 'all 0.2s'
                    }}
                    onMouseEnter={(e) => {
                      if (!selectedIds.includes(item.id)) {
                        e.currentTarget.style.backgroundColor = '#222';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!selectedIds.includes(item.id)) {
                        e.currentTarget.style.backgroundColor = '#1a1a1a';
                      }
                    }}
                  >
                    {/* 选择框和标题 */}
                    <div style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '6px',
                      marginBottom: '6px'
                    }}>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(item.id)}
                        onChange={() => handleSelectItem(item.id)}
                        style={{
                          width: '12px',
                          height: '12px',
                          marginTop: '2px',
                          accentColor: '#3bb0e6'
                        }}
                        onClick={(e) => e.stopPropagation()}
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        {editingId === item.id ? (
                          <input
                            type="text"
                            value={editingTitle}
                            onChange={(e) => setEditingTitle(e.target.value)}
                            onBlur={() => {
                              if (editingTitle.trim()) {
                                handleRenameItem(item.id, editingTitle.trim());
                              } else {
                                setEditingId(null);
                                setEditingTitle('');
                              }
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                if (editingTitle.trim()) {
                                  handleRenameItem(item.id, editingTitle.trim());
                                } else {
                                  setEditingId(null);
                                  setEditingTitle('');
                                }
                              } else if (e.key === 'Escape') {
                                setEditingId(null);
                                setEditingTitle('');
                              }
                            }}
                            autoFocus
                            style={{
                              fontSize: '12px',
                              fontWeight: '500',
                              color: '#fff',
                              background: '#333',
                              border: '1px solid #3bb0e6',
                              borderRadius: '3px',
                              padding: '2px 4px',
                              width: '100%',
                              marginBottom: '4px'
                            }}
                            onClick={(e) => e.stopPropagation()}
                          />
                        ) : (
                          <div style={{
                            fontSize: '12px',
                            fontWeight: '500',
                            color: '#fff',
                            marginBottom: '4px',
                            lineHeight: '1.3',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical'
                          }}>
                            {item.title}
                          </div>
                        )}
                        <div style={{
                          fontSize: '10px',
                          color: '#666',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px'
                        }}>
                          <span>{new Date(item.timestamp).toLocaleDateString('zh-CN', {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}</span>
                        </div>
                      </div>
                      
                      {/* 右侧操作按钮 */}
                      <div style={{ position: 'relative' }}>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveMenuId(activeMenuId === item.id ? null : item.id);
                          }}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: '#666',
                            cursor: 'pointer',
                            padding: '4px',
                            fontSize: '14px',
                            lineHeight: 1,
                            borderRadius: '3px',
                            transition: 'all 0.2s'
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.color = '#999';
                            e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.color = '#666';
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                        >
                          ···
                        </button>
                        
                        {/* 下拉菜单 */}
                        {activeMenuId === item.id && (
                          <div style={{
                            position: 'absolute',
                            top: '100%',
                            right: '0',
                            backgroundColor: '#2a2a2a',
                            border: '1px solid #444',
                            borderRadius: '6px',
                            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                            zIndex: 1000,
                            minWidth: '80px',
                            overflow: 'hidden'
                          }}>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handlePinItem(item.id);
                              }}
                              style={{
                                width: '100%',
                                padding: '8px 12px',
                                background: 'none',
                                border: 'none',
                                color: '#fff',
                                fontSize: '12px',
                                textAlign: 'left',
                                cursor: 'pointer',
                                transition: 'background-color 0.2s'
                              }}
                              onMouseEnter={(e) => {
                                e.currentTarget.style.backgroundColor = '#333';
                              }}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.backgroundColor = 'transparent';
                              }}
                            >
                              Pin
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                startRenaming(item);
                              }}
                              style={{
                                width: '100%',
                                padding: '8px 12px',
                                background: 'none',
                                border: 'none',
                                color: '#fff',
                                fontSize: '12px',
                                textAlign: 'left',
                                cursor: 'pointer',
                                transition: 'background-color 0.2s'
                              }}
                              onMouseEnter={(e) => {
                                e.currentTarget.style.backgroundColor = '#333';
                              }}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.backgroundColor = 'transparent';
                              }}
                            >
                              Rename
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
      {/* 中间聊天区域 */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: '400px'
      }}>
        {/* 顶部标题栏 */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid #333',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          position: 'relative'
        }}>
          {/* My折叠面板控制按钮 - 移到最左侧，无边框，横线左对齐 */}
          <button
            onClick={() => setIsMyPanelCollapsed(!isMyPanelCollapsed)}
            style={{
              position: 'absolute',
              left: '20px',
              padding: '8px',
              borderRadius: '6px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-start',
              width: '36px',
              height: '36px',
              transition: 'all 0.2s ease',
              flexDirection: 'column',
              gap: '2px'
            }}
            title={isMyPanelCollapsed ? 'Expand recent history' : 'Collapse recent history'}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(161,161,170,0.1)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
            }}
          >
            {/* 三条长短不一的横杠 - 左对齐 */}
            <div style={{
              width: '16px',
              height: '2px',
              backgroundColor: '#a1a1aa',
              borderRadius: '1px',
              alignSelf: 'flex-start',
              transition: 'all 0.2s ease'
            }} />
            <div style={{
              width: '12px',
              height: '2px',
              backgroundColor: '#a1a1aa',
              borderRadius: '1px',
              alignSelf: 'flex-start',
              transition: 'all 0.2s ease'
            }} />
            <div style={{
              width: '20px',
              height: '2px',
              backgroundColor: '#a1a1aa',
              borderRadius: '1px',
              alignSelf: 'flex-start',
              transition: 'all 0.2s ease'
            }} />
          </button>
          
          {/* 居中的Veritex标题 - 可点击返回首页，更大字号 */}
          <button 
            onClick={() => navigate('/')}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0
            }}
          >
            <h1 style={{ 
              margin: 0, 
              fontSize: '32px', 
              color: '#3bb0e6',
              fontWeight: '700',
              letterSpacing: '1px',
              textAlign: 'center',
              transition: 'all 0.2s ease'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#52c8f5';
              e.currentTarget.style.textShadow = '0 0 8px rgba(59,176,230,0.3)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#3bb0e6';
              e.currentTarget.style.textShadow = 'none';
            }}
            >
              Veritex
            </h1>
          </button>
          
          {/* 右侧按钮 */}
          <div style={{ position: 'absolute', right: '20px', display: 'flex', gap: '8px' }}>
            {/* 侧边栏折叠/展开按钮 */}
            <button
              onClick={() => setIsKeywordPanelCollapsed(!isKeywordPanelCollapsed)}
              style={{
                padding: '6px 8px',
                borderRadius: '6px',
                border: '1px solid #666',
                background: 'transparent',
                color: '#3bb0e6',
                cursor: 'pointer',
                fontSize: '14px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                minWidth: '32px',
                transition: 'all 0.2s ease'
              }}
              title={isKeywordPanelCollapsed ? '展开关键词面板' : '关闭关键词面板'}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#3bb0e6';
                e.currentTarget.style.backgroundColor = 'rgba(59,176,230,0.1)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#666';
                e.currentTarget.style.backgroundColor = 'transparent';
              }}
            >
              {isKeywordPanelCollapsed ? '◀' : '▶'}
            </button>
          </div>
        </div>

        {/* 消息区域 */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px'
        }}>
          {messages.map((message) => (
            <div
              key={message.id}
              style={{
                display: 'flex',
                justifyContent: message.isUser ? 'flex-end' : 'flex-start',
                alignItems: 'flex-start',
                gap: '12px'
              }}
            >
              {/* 头像 */}
              {!message.isUser && (
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  backgroundColor: '#3bb0e6',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '16px',
                  flexShrink: 0
                }}>
                  🤖
                </div>
              )}

              {/* 消息气泡 */}
              <div style={{
                maxWidth: '70%',
                backgroundColor: message.isUser ? '#3bb0e6' : '#1a1a1a',
                color: message.isUser ? '#fff' : '#e5e5e5',
                padding: '12px 16px',
                borderRadius: message.isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                fontSize: '14px',
                lineHeight: '1.6',
                whiteSpace: message.isUser ? 'pre-wrap' : 'normal',
                border: message.isUser ? 'none' : '1px solid #333'
              }}>
                {message.isUser ? (
                  <div>{message.text}</div>
                ) : (
                  <ReactMarkdown
                    components={{
                      // 自定义组件样式，适配深色主题
                      h1: ({ children }) => <h1 style={{ color: '#e5e5e5', fontSize: '18px', marginBottom: '12px' }}>{children}</h1>,
                      h2: ({ children }) => <h2 style={{ color: '#e5e5e5', fontSize: '16px', marginBottom: '10px' }}>{children}</h2>,
                      h3: ({ children }) => <h3 style={{ color: '#e5e5e5', fontSize: '15px', marginBottom: '8px' }}>{children}</h3>,
                      p: ({ children }) => <p style={{ color: '#e5e5e5', marginBottom: '8px', lineHeight: '1.6' }}>{children}</p>,
                      strong: ({ children }) => <strong style={{ color: '#fff', fontWeight: '600' }}>{children}</strong>,
                      em: ({ children }) => <em style={{ color: '#e5e5e5', fontStyle: 'italic' }}>{children}</em>,
                      ul: ({ children }) => <ul style={{ color: '#e5e5e5', paddingLeft: '20px', marginBottom: '8px' }}>{children}</ul>,
                      ol: ({ children }) => <ol style={{ color: '#e5e5e5', paddingLeft: '20px', marginBottom: '8px' }}>{children}</ol>,
                      li: ({ children }) => <li style={{ color: '#e5e5e5', marginBottom: '4px' }}>{children}</li>,
                      code: ({ children }) => (
                        <code style={{
                          backgroundColor: '#333',
                          color: '#fff',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          fontSize: '13px',
                          fontFamily: 'monospace'
                        }}>{children}</code>
                      ),
                      pre: ({ children }) => (
                        <pre style={{
                          backgroundColor: '#333',
                          color: '#fff',
                          padding: '12px',
                          borderRadius: '8px',
                          overflow: 'auto',
                          fontSize: '13px',
                          fontFamily: 'monospace',
                          marginBottom: '12px'
                        }}>{children}</pre>
                      ),
                      blockquote: ({ children }) => (
                        <blockquote style={{
                          borderLeft: '3px solid #3bb0e6',
                          paddingLeft: '12px',
                          margin: '8px 0',
                          color: '#ccc',
                          fontStyle: 'italic'
                        }}>{children}</blockquote>
                      )
                    }}
                  >
                    {message.text}
                  </ReactMarkdown>
                )}
                
                {/* 时间戳 */}
                <div style={{
                  fontSize: '11px',
                  color: message.isUser ? 'rgba(255,255,255,0.7)' : '#666',
                  marginTop: '8px',
                  textAlign: message.isUser ? 'right' : 'left'
                }}>
                  {formatTime(message.timestamp)}
                </div>

                {/* 如果有学术分析结果，显示提示 */}
                {message.hierarchicalKeywords && (
                  <div style={{
                    marginTop: '12px',
                    padding: '8px 12px',
                    backgroundColor: 'rgba(59,176,230,0.1)',
                    borderRadius: '8px',
                    border: '1px solid rgba(59,176,230,0.2)',
                    fontSize: '12px'
                  }}>
                    💡 已为您分析并扩展关键词，请查看右侧关键词云进行搜索
                  </div>
                )}
              </div>

              {/* 用户头像 */}
              {message.isUser && (
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  backgroundColor: '#666',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '16px',
                  flexShrink: 0
                }}>
                  👤
                </div>
              )}
            </div>
          ))}

          {/* 加载指示器 */}
          {isLoading && (
            <div style={{
              display: 'flex',
              justifyContent: 'flex-start',
              alignItems: 'center',
              gap: '12px'
            }}>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                backgroundColor: '#3bb0e6',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '16px'
              }}>
                🤖
              </div>
              <div style={{
                backgroundColor: '#1a1a1a',
                padding: '12px 16px',
                borderRadius: '16px 16px 16px 4px',
                border: '1px solid #333'
              }}>
                <div style={{
                  display: 'flex',
                  gap: '4px',
                  alignItems: 'center'
                }}>
                  <div style={{ fontSize: '12px', color: '#666' }}>AI正在思考</div>
                  <div style={{
                    display: 'flex',
                    gap: '2px'
                  }}>
                    {[0, 1, 2].map(i => (
                      <div
                        key={i}
                        style={{
                          width: '4px',
                          height: '4px',
                          backgroundColor: '#3bb0e6',
                          borderRadius: '50%',
                          animation: `pulse 1.5s ease-in-out ${i * 0.3}s infinite`
                        }}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* 输入区域 */}
        <div style={{
          padding: '16px 20px',
          borderTop: '1px solid #333',
          backgroundColor: '#0a0a0a'
        }}>
          <div style={{
            display: 'flex',
            gap: '12px',
            alignItems: 'flex-end',
            position: 'relative'
          }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="输入您的学术问题或研究主题..."
                disabled={isLoading}
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  borderRadius: '12px',
                  border: '1px solid #333',
                  backgroundColor: '#1a1a1a',
                  color: '#fff',
                  fontSize: '14px',
                  lineHeight: '1.5',
                  resize: 'none',
                  minHeight: '44px',
                  maxHeight: '120px',
                  outline: 'none',
                  fontFamily: 'inherit'
                }}
                rows={1}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = 'auto';
                  target.style.height = Math.min(target.scrollHeight, 120) + 'px';
                }}
              />
            </div>
            
            <button
              onClick={handleSendMessage}
              disabled={isLoading || !inputMessage.trim()}
              style={{
                padding: '12px 20px',
                borderRadius: '12px',
                border: 'none',
                backgroundColor: inputMessage.trim() && !isLoading ? '#3bb0e6' : '#666',
                color: '#fff',
                cursor: inputMessage.trim() && !isLoading ? 'pointer' : 'not-allowed',
                fontSize: '14px',
                fontWeight: '600',
                transition: 'all 0.2s',
                minWidth: '80px'
              }}
            >
              {isLoading ? '...' : '发送'}
            </button>
          </div>
          
          <div style={{
            marginTop: '8px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            
            {/* 详细的token使用情况 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <TokenProgress messages={messages} size={20} showText={true} />
            </div>
          </div>
        </div>
      </div>

      {/* 右侧关键词云区域 */}
      {!isKeywordPanelCollapsed && (
        <>
          {/* 拖拽分隔条 */}
          <div
            style={{
              width: '4px',
              cursor: 'ew-resize',
              backgroundColor: isResizing ? '#3bb0e6' : 'transparent',
              borderLeft: '1px solid #333',
              transition: 'background-color 0.2s',
              position: 'relative'
            }}
            onMouseDown={() => setIsResizing(true)}
          >
            <div style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              width: '20px',
              height: '40px',
              background: isResizing ? '#3bb0e6' : '#666',
              borderRadius: '10px',
              opacity: 0.6,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '12px',
              color: '#fff'
            }}>
              ⋮
            </div>
          </div>
          
          <div style={{
            width: `${keywordPanelWidth}px`,
            height: '100vh',
            borderLeft: '1px solid #333',
            backgroundColor: '#0a0a0a',
            position: 'relative',
            transition: isResizing ? 'none' : 'width 0.3s ease',
            display: 'flex',
            flexDirection: 'column'
          }}>
            {/* 关键词云面板头部 */}
            <div style={{
              padding: '12px 16px',
              borderBottom: '1px solid #333',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              backgroundColor: '#111'
            }}>
              <h3 style={{ 
                margin: 0, 
                fontSize: '14px', 
                fontWeight: '600',
                color: '#fff'
              }}>
                Keywords & Search
              </h3>
            </div>
            
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <KeywordCloudWidget 
                hierarchicalKeywords={currentAnalysis?.hierarchical_keywords || null}
                originalQuery=""
                isDraggable={true}
              />
            </div>
          </div>
        </>
      )}
      

      {/* 动画样式 */}
      <style>
        {`
          @keyframes pulse {
            0%, 100% { opacity: 0.4; transform: scale(0.8); }
            50% { opacity: 1; transform: scale(1.2); }
          }
        `}
      </style>
    </div>
  );
};

export default ChatInterface;