import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { apiCall, API_CONFIG } from './config';
import KeywordCloudWidget from './components/KeywordCloudWidget';
import TokenProgress from './components/TokenProgress';
import { useGlobal } from './contexts/GlobalContext';
// 定义历史记录相关的类型
interface HistoryItem {
  id: string;
  timestamp: number;
  type: 'search' | 'chat';
  title: string;
  data: SearchHistory | ChatHistory;
}

interface SearchHistory {
  id: string;
  timestamp: number;
  originalQuery: string;
  expandedKeywords: string[];
  papers: any[];
  maxResults: number;
}

interface ChatHistory {
  id: string;
  timestamp: number;
  title: string;
  messages: any[];
  lastActivity: number;
}
import { UserStorage, DataMigration, USER_DATA_KEYS, GLOBAL_DATA_KEYS } from './utils/userStorage';
import { calculateTokenUsage, MAX_TOKENS } from './utils/tokenCounter';

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: number;
  analysisResult?: any;
  hierarchicalKeywords?: any;
  isEditing?: boolean;
  searchResults?: any[];
  searchMetadata?: {
    originalQuery: string;
    expandedKeywords: string[];
    maxResults: number;
    analysisResult: any;
  };
}

interface ChatInterfaceProps {
  className?: string;
}

// 防抖函数
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

// Markdown完整性检查
const isMarkdownComplete = (text: string): boolean => {
  // 检查配对的markdown标记
  const boldMarks = (text.match(/\*\*/g) || []).length;
  const italicMarks = (text.match(/(?<!\*)\*(?!\*)/g) || []).length;
  const codeBlocks = (text.match(/```/g) || []).length;
  const inlineCode = (text.match(/(?<!`)`(?!`)/g) || []).length;
  
  // 检查是否配对
  return boldMarks % 2 === 0 && 
         italicMarks % 2 === 0 && 
         codeBlocks % 2 === 0 && 
         inlineCode % 2 === 0;
};

// 使用用户隔离存储键名
const CHAT_STORAGE_KEY = USER_DATA_KEYS.CHAT_HISTORY;
const CHAT_ANALYSIS_KEY = USER_DATA_KEYS.CURRENT_ANALYSIS;

const ChatInterface: React.FC<ChatInterfaceProps> = ({ className = '' }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, toggleTheme } = useGlobal();
  const [messages, setMessages] = useState<Message[]>([]);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState<string>('');
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentAnalysis, setCurrentAnalysis] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // 流式传输相关状态
  const [streamingText, setStreamingText] = useState('');
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const debouncedStreamingText = useDebounce(streamingText, 100); // 100ms 防抖
  
  // 关键词云面板状态
  const [isKeywordPanelCollapsed, setIsKeywordPanelCollapsed] = useState(false);
  const [keywordPanelWidth, setKeywordPanelWidth] = useState(380);
  const [isResizing, setIsResizing] = useState(false);

  // 自动折叠逻辑 - 监听面板宽度变化（更保守的阈值）
  useEffect(() => {
    // 只有在极小宽度时才自动折叠，避免误折叠
    if (keywordPanelWidth < 180 && !isKeywordPanelCollapsed) {
      setIsKeywordPanelCollapsed(true);
    }
    // 当宽度足够大时自动展开
    if (keywordPanelWidth >= 300 && isKeywordPanelCollapsed) {
      setIsKeywordPanelCollapsed(false);
    }
  }, [keywordPanelWidth, isKeywordPanelCollapsed]);

  // 处理防抖后的流式文本更新
  useEffect(() => {
    if (streamingMessageId && debouncedStreamingText) {
      // 检查markdown完整性，如果不完整则显示为纯文本
      const textToDisplay = isMarkdownComplete(debouncedStreamingText) 
        ? debouncedStreamingText 
        : debouncedStreamingText.replace(/\*\*/g, ''); // 移除不完整的粗体标记
      
      setMessages(prev => prev.map(msg => 
        msg.id === streamingMessageId 
          ? { ...msg, text: textToDisplay }
          : msg
      ));
    }
  }, [debouncedStreamingText, streamingMessageId]);
  
  // My面板状态
  const [isMyPanelCollapsed, setIsMyPanelCollapsed] = useState(false);
  const [myPanelWidth] = useState(300);
  const [isMobile, setIsMobile] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  
  // My面板历史记录状态
  const [unifiedHistory, setUnifiedHistory] = useState<HistoryItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [filter, setFilter] = useState<'search' | 'chat'>('search');
  
  // 操作菜单状态
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>('');
  
  // LLM模式状态（全局共享）
  const [llmMode, setLlmMode] = useState<'auto-search' | 'chat-plan'>(() => {
    const saved = UserStorage.getGlobalData(GLOBAL_DATA_KEYS.LLM_MODE);
    return (saved as 'auto-search' | 'chat-plan') || 'auto-search';
  });
  
  // 从首页传来的初始输入
  const initialInput = location.state?.input || '';
  const preserveChat = location.state?.preserveChat || false;
  
  // 生成用户头像字母（基于内测码首字母）
  const generateAvatar = (userId: string) => {
    if (!userId) return '?'
    const firstChar = userId.charAt(0).toUpperCase()
    return /[A-Z0-9]/.test(firstChar) ? firstChar : '?'
  }
  
  // 处理登出
  const handleLogout = () => {
    localStorage.removeItem('invite_logged_in')
    localStorage.removeItem('user_id')
    setShowUserMenu(false)
    navigate('/')
  }

  // 保存聊天记录到用户隔离存储（会话级别）
  const saveChatHistory = (messages: Message[], analysis: any = null) => {
    console.log('💬 保存聊天记录到用户隔离存储')
    UserStorage.setUserData(CHAT_STORAGE_KEY, JSON.stringify(messages));
    if (analysis) {
      UserStorage.setUserData(CHAT_ANALYSIS_KEY, JSON.stringify(analysis));
    }
    
    // 保存完整对话会话到统一历史记录
    saveChatSessionToHistory(messages);
  };

  // 打开关键词云并加载指定消息的历史关键词
  const handleShowKeywords = (message: Message) => {
    const hk = message.hierarchicalKeywords 
      || message.searchMetadata?.analysisResult?.hierarchical_keywords 
      || null;
    if (!hk) {
      return;
    }
    setCurrentAnalysis({ hierarchical_keywords: hk });
    setIsKeywordPanelCollapsed(false);
    setKeywordPanelWidth((w) => (w < 300 ? 300 : w));
  };

  // 超过token阈值时的引导（4000 tokens）
  const { totalTokens } = calculateTokenUsage(messages);
  const isContextOverloaded = totalTokens >= MAX_TOKENS;

  const handleStartNewTopic = () => {
    // 清除当前聊天并开始新的搜索
    UserStorage.removeUserData(CHAT_STORAGE_KEY);
    UserStorage.removeUserData(CHAT_ANALYSIS_KEY);
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
    // 滚动到底部
    setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 0);
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
      // 🔐 使用用户隔离存储
      const CHAT_STORAGE_KEY_UNIFIED = USER_DATA_KEYS.CHAT_HISTORY_UNIFIED;
      const UNIFIED_HISTORY_KEY = USER_DATA_KEYS.UNIFIED_HISTORY;
      
      // 更新或创建聊天会话记录
      const existingChatHistory = JSON.parse(UserStorage.getUserData(CHAT_STORAGE_KEY_UNIFIED) || '[]');
      const existingIndex = existingChatHistory.findIndex((item: any) => item.id === sessionId);
      
      if (existingIndex >= 0) {
        existingChatHistory[existingIndex] = chatSession;
      } else {
        existingChatHistory.unshift(chatSession);
      }
      
      if (existingChatHistory.length > 50) {
        existingChatHistory.splice(50);
      }
      UserStorage.setUserData(CHAT_STORAGE_KEY_UNIFIED, JSON.stringify(existingChatHistory));
      
      // 保存到统一历史
      const unifiedItem = {
        id: sessionId,
        timestamp: chatSession.lastActivity,
        type: 'chat' as const,
        title: title,
        data: chatSession
      };
      
      const existingUnifiedHistory = JSON.parse(UserStorage.getUserData(UNIFIED_HISTORY_KEY) || '[]');
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
      UserStorage.setUserData(UNIFIED_HISTORY_KEY, JSON.stringify(existingUnifiedHistory));
      
      // 🔄 更新UI中的历史记录
      loadUnifiedHistory();
      
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
      // 🔐 使用用户隔离存储
      const SEARCH_STORAGE_KEY = USER_DATA_KEYS.SEARCH_HISTORY;
      const UNIFIED_HISTORY_KEY = USER_DATA_KEYS.UNIFIED_HISTORY;
      
      // 保存到搜索历史
      const existingSearchHistory = JSON.parse(UserStorage.getUserData(SEARCH_STORAGE_KEY) || '[]');
      existingSearchHistory.unshift(searchHistory);
      
      if (existingSearchHistory.length > 50) {
        existingSearchHistory.splice(50);
      }
      UserStorage.setUserData(SEARCH_STORAGE_KEY, JSON.stringify(existingSearchHistory));
      
      // 保存到统一历史
      // 使用Exact Terms作为Search results的标题
      const exactTermsArray = response.analysis_result?.hierarchical_keywords?.exact_terms?.terms || [];
      const exactTermsString = exactTermsArray.length > 0 ? exactTermsArray.join(', ') : userQuery;
      const exactTerms = exactTermsString;
      const unifiedItem = {
        id: searchId,
        timestamp: searchHistory.timestamp,
        type: 'search' as const,
        title: exactTerms.length > 50 ? exactTerms.slice(0, 50) + '...' : exactTerms,
        data: searchHistory
      };
      
      const existingUnifiedHistory = JSON.parse(UserStorage.getUserData(UNIFIED_HISTORY_KEY) || '[]');
      existingUnifiedHistory.unshift(unifiedItem);
      
      existingUnifiedHistory.sort((a: any, b: any) => b.timestamp - a.timestamp);
      
      if (existingUnifiedHistory.length > 100) {
        existingUnifiedHistory.splice(100);
      }
      UserStorage.setUserData(UNIFIED_HISTORY_KEY, JSON.stringify(existingUnifiedHistory));
      
      // 🔄 更新UI中的历史记录
      loadUnifiedHistory();
      
    } catch (error) {
      console.error('Error saving search result to history:', error);
    }
  };

  // 从用户隔离存储恢复聊天记录
  const loadChatHistory = (): { messages: Message[], analysis: any } => {
    try {
      console.log('📥 从用户隔离存储加载聊天记录')
      const savedMessages = UserStorage.getUserData(CHAT_STORAGE_KEY);
      const savedAnalysis = UserStorage.getUserData(CHAT_ANALYSIS_KEY);
      
      let messages: Message[] = savedMessages ? JSON.parse(savedMessages) : [];
      
      // 🔧 数据完整性检查和修复
      if (messages.length > 0) {
        console.log('🔍 检查消息数据完整性...')
        let hasRepairs = false;
        
        messages = messages.map((message) => {
          // 检查搜索结果相关的消息是否完整
          if (!message.isUser && message.text && message.text.includes('为您找到了') && !message.searchResults) {
            console.log(`⚠️ 发现消息 ${message.id} 缺少搜索结果数据，尝试从搜索历史恢复...`)
            
            // 尝试从搜索历史中恢复数据
            try {
              const searchHistory = JSON.parse(UserStorage.getUserData(USER_DATA_KEYS.SEARCH_HISTORY) || '[]');
              // 根据时间戳匹配最近的搜索记录
              const matchingSearch = searchHistory.find((search: any) => 
                Math.abs(search.timestamp - message.timestamp) < 60000 // 1分钟内的搜索
              );
              
              if (matchingSearch) {
                console.log(`✅ 从搜索历史恢复了消息 ${message.id} 的搜索结果`)
                message.searchResults = matchingSearch.papers || [];
                message.searchMetadata = {
                  originalQuery: matchingSearch.originalQuery || '',
                  expandedKeywords: matchingSearch.expandedKeywords || [],
                  maxResults: matchingSearch.maxResults || 0,
                  analysisResult: matchingSearch.analysisResult || null
                };
                hasRepairs = true;
              }
            } catch (repairError) {
              console.warn('搜索结果数据恢复失败:', repairError);
            }
          }
          
          return message;
        });
        
        // 如果有修复，重新保存消息
        if (hasRepairs) {
          console.log('💾 保存修复后的消息数据')
          UserStorage.setUserData(CHAT_STORAGE_KEY, JSON.stringify(messages));
        }
      }
      
      return {
        messages,
        analysis: savedAnalysis ? JSON.parse(savedAnalysis) : null
      };
    } catch (error) {
      console.error('Error loading chat history:', error);
      return { messages: [], analysis: null };
    }
  };

  // 加载统一历史记录（用于My面板）
  const loadUnifiedHistory = () => {
    try {
      console.log('📥 从用户隔离存储加载统一历史记录')
      const savedHistory = UserStorage.getUserData(USER_DATA_KEYS.UNIFIED_HISTORY);
      const historyData = savedHistory ? JSON.parse(savedHistory) : [];
      setUnifiedHistory(historyData);
    } catch (error) {
      console.error('Error loading unified history:', error);
      setUnifiedHistory([]);
    }
  };

  // 清除聊天历史

  // 初始化聊天记录
  useEffect(() => {
    // 🔄 自动检查并迁移旧数据
    DataMigration.autoMigrate();
    
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
    
    // 🔄 加载My面板的历史记录
    loadUnifiedHistory();
    
    // 如果有来自首页的初始输入，设置到输入框中
    if (initialInput && !preserveChat) {
      // 只有在不保留聊天记录的情况下才设置初始输入
      setInputMessage(initialInput);
    } else if (initialInput && preserveChat) {
      // 如果需要保留聊天记录且有新输入，直接设置到输入框
      setInputMessage(initialInput);
    }
  }, [initialInput, preserveChat]);

  // LLM模式切换快捷键监听
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.shiftKey && event.key === 'Tab') {
        event.preventDefault();
        
        // 切换模式
        const newMode = llmMode === 'auto-search' ? 'chat-plan' : 'auto-search';
        setLlmMode(newMode);
        
        // 保存到全局存储（所有用户共享）
        UserStorage.setGlobalData(GLOBAL_DATA_KEYS.LLM_MODE, newMode);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [llmMode]);

  // 监听页面可见性变化，确保从其他页面返回时刷新历史记录
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        // 页面重新获得焦点时刷新My面板历史记录
        loadUnifiedHistory();
        console.log('📱 页面重新获得焦点，刷新My面板历史记录');
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);


  // 加载My面板历史记录
  const loadMyPanelHistory = async () => {
    const userId = localStorage.getItem('user_id');
    if (!userId) {
      setUnifiedHistory([]);
      return;
    }
    try {
      // 🔐 使用用户隔离存储
      loadUnifiedHistory();
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
    
    // 初始化时检查一次
    handleResize();
    
    window.addEventListener('resize', handleResize);
    
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
          // 删除选中的历史记录
          const historyData = UserStorage.getUserData(USER_DATA_KEYS.UNIFIED_HISTORY);
          if (historyData) {
            const history: HistoryItem[] = JSON.parse(historyData);
            const filteredHistory = history.filter(item => !selectedIds.includes(item.id));
            UserStorage.setUserData(USER_DATA_KEYS.UNIFIED_HISTORY, JSON.stringify(filteredHistory));
          }
          setSelectedIds([]);
          setSelectAll(false);
          await loadMyPanelHistory();
        } catch (error) {
          console.error('Delete failed:', error);
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
      try {
        // 使用用户隔离存储，避免整页刷新，确保即时渲染
        UserStorage.setUserData(USER_DATA_KEYS.CHAT_HISTORY, JSON.stringify(chatData.messages));
      } catch (error) {
        console.error('保存聊天记录失败:', error);
      }
      setMessages(chatData.messages);
      setCurrentAnalysis(null);
      setActiveMenuId(null);
      // 平滑滚动到底部
      setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 0);
    }
  };

  // 置顶功能
  const handlePinItem = async (itemId: string) => {
    try {
      // 🔐 使用用户隔离存储
      const UNIFIED_HISTORY_KEY = USER_DATA_KEYS.UNIFIED_HISTORY;
      const existingHistory = JSON.parse(UserStorage.getUserData(UNIFIED_HISTORY_KEY) || '[]');
      
      // 找到要置顶的项目
      const itemToPin = existingHistory.find((item: any) => item.id === itemId);
      if (!itemToPin) return;
      
      // 更新时间戳为当前时间，实现置顶效果
      const updatedItem = { ...itemToPin, timestamp: Date.now() };
      
      // 更新历史记录
      const updatedHistory = existingHistory.map((h: any) => 
        h.id === itemId ? updatedItem : h
      ).sort((a: any, b: any) => b.timestamp - a.timestamp);
      
      UserStorage.setUserData(UNIFIED_HISTORY_KEY, JSON.stringify(updatedHistory));
      
      // 🔄 更新UI
      setUnifiedHistory(updatedHistory);
      setActiveMenuId(null);
    } catch (error) {
      console.error('Pin item failed:', error);
    }
  };

  // 重命名功能
  const handleRenameItem = async (itemId: string, newTitle: string) => {
    try {
      // 🔐 使用用户隔离存储
      const UNIFIED_HISTORY_KEY = USER_DATA_KEYS.UNIFIED_HISTORY;
      const existingHistory = JSON.parse(UserStorage.getUserData(UNIFIED_HISTORY_KEY) || '[]');
      const updatedHistory = existingHistory.map((h: any) => 
        h.id === itemId ? { ...h, title: newTitle } : h
      );
      
      UserStorage.setUserData(UNIFIED_HISTORY_KEY, JSON.stringify(updatedHistory));
      
      // 同时更新对应的具体历史记录
      if (itemId.startsWith('search_')) {
        const SEARCH_STORAGE_KEY = USER_DATA_KEYS.SEARCH_HISTORY;
        const searchHistory = JSON.parse(UserStorage.getUserData(SEARCH_STORAGE_KEY) || '[]');
        const updatedSearchHistory = searchHistory.map((s: any) => 
          s.id === itemId ? { ...s, customTitle: newTitle } : s
        );
        UserStorage.setUserData(SEARCH_STORAGE_KEY, JSON.stringify(updatedSearchHistory));
      } else if (itemId.startsWith('chat_')) {
        const CHAT_STORAGE_KEY = USER_DATA_KEYS.CHAT_HISTORY_UNIFIED;
        const chatHistory = JSON.parse(UserStorage.getUserData(CHAT_STORAGE_KEY) || '[]');
        const updatedChatHistory = chatHistory.map((c: any) => 
          c.id === itemId ? { ...c, title: newTitle } : c
        );
        UserStorage.setUserData(CHAT_STORAGE_KEY, JSON.stringify(updatedChatHistory));
      }
      
      // 🔄 更新UI
      setUnifiedHistory(updatedHistory);
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
      const minWidth = 300; // 增加最小宽度，避免过小
      const maxWidth = Math.min(600, window.innerWidth * 0.5); // 限制最大宽度
      
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

  // 点击外部关闭用户菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (showUserMenu) {
        const target = event.target as Element
        if (!target.closest('.user-menu-container')) {
          setShowUserMenu(false)
        }
      }
    }
    
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showUserMenu]);

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

  // 流式传输状态
  const [isStreaming, setIsStreaming] = useState(false);

  // 处理流式响应
  const handleStreamingResponse = async (userMessage: Message, newMessages: Message[]) => {
    // 重置流式传输状态
    setStreamingText('');
    
    const mappedHistory = newMessages.map(m => ({
      role: m.isUser ? 'user' : 'assistant',
      content: m.text
    }));

    const payload = {
      message: userMessage.text,
      history: mappedHistory,
      mode: llmMode === 'chat-plan' ? 'chat-only' : 'auto-search',
      stream: true // 启用流式传输
    };

    // 创建初始的助手消息
    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      text: '',
      isUser: false,
      timestamp: Date.now() + 1
    };

    // 设置当前流式消息ID
    setStreamingMessageId(assistantMessage.id);

    const messagesWithAssistant = [...newMessages, assistantMessage];
    setMessages(messagesWithAssistant);

    try {
      const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.CHAT}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('无法获取响应流');
      }

      const decoder = new TextDecoder();
      let buffer = '';
      let accumulatedText = '';
      let analysisResult = null;
      let searchResults = null;
      let isAcademicQuery = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'start') {
                // 流式开始
                console.log('流式传输开始');
              } else if (data.type === 'status') {
                // 状态更新（可以显示给用户）
                console.log('状态更新:', data.data.message);
              } else if (data.type === 'content') {
                // 内容片段
                accumulatedText += data.data.content;
                
                // 使用防抖更新，减少重渲染
                setStreamingText(accumulatedText);
                
                // 自动滚动到底部
                setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 0);
                
              } else if (data.type === 'done') {
                // 流式完成
                isAcademicQuery = data.data.is_academic_query || false;
                searchResults = data.data.search_results || null;
                analysisResult = data.data.analysis_result || null;
                
                console.log('流式传输完成');
              } else if (data.type === 'error') {
                // 错误处理
                throw new Error(data.data.error);
              }
            } catch (e) {
              console.error('解析SSE数据失败:', e);
            }
          }
        }
      }

      // 流式完成后更新最终消息
      let hierarchicalKeywords = null;
      if (analysisResult && analysisResult.hierarchical_keywords) {
        hierarchicalKeywords = analysisResult.hierarchical_keywords;
        setCurrentAnalysis(analysisResult);
      }

      // 清理流式传输状态
      setStreamingMessageId(null);
      setStreamingText('');

      const finalAssistantMessage: Message = {
        ...assistantMessage,
        text: accumulatedText || '抱歉，我无法处理您的请求。',
        analysisResult,
        hierarchicalKeywords
      };

      // 如果是学术查询并有搜索结果
      if (isAcademicQuery && searchResults && searchResults.length > 0) {
        saveSearchResultToHistory(userMessage.text, {
          search_results: searchResults,
          analysis_result: analysisResult,
          is_academic_query: isAcademicQuery
        });
        
        finalAssistantMessage.searchResults = searchResults;
        finalAssistantMessage.searchMetadata = {
          originalQuery: userMessage.text,
          expandedKeywords: analysisResult?.hierarchical_keywords ? 
            Object.values(analysisResult.hierarchical_keywords).flatMap((level: any) => level.terms || []) : [],
          maxResults: searchResults.length,
          analysisResult
        };
      }

      const finalMessages = [...newMessages, finalAssistantMessage];
      setMessages(finalMessages);
      saveChatHistory(finalMessages, analysisResult);

    } catch (error) {
      console.error('流式传输错误:', error);
      
      // 错误情况下更新消息
      const errorMessage = {
        ...assistantMessage,
        text: `抱歉，发生了错误：${error instanceof Error ? error.message : '未知错误'}`
      };
      
      const errorMessages = [...newMessages, errorMessage];
      setMessages(errorMessages);
      saveChatHistory(errorMessages, currentAnalysis);
    }
  };

  // 发送消息
  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isStreaming) return;

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
    setIsStreaming(true);

    try {
      // 使用流式传输
      await handleStreamingResponse(userMessage, newMessages);
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
      setIsStreaming(false);
    }
  };


  // 处理键盘事件
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // 开始编辑消息
  const startEditMessage = (message: Message) => {
    setEditingMessageId(message.id);
    setEditingText(message.text);
  };

  // 取消编辑
  const cancelEdit = () => {
    setEditingMessageId(null);
    setEditingText('');
  };

  // 保存编辑
  const saveEdit = async () => {
    if (editingMessageId && editingText.trim()) {
      // 找到要编辑的消息索引
      const messageIndex = messages.findIndex(m => m.id === editingMessageId);
      if (messageIndex !== -1) {
        // 创建新的消息数组，保留到编辑消息之前的所有消息
        const newMessages = messages.slice(0, messageIndex);
        
        // 添加编辑后的用户消息
        const editedMessage: Message = {
          ...messages[messageIndex],
          text: editingText.trim()
        };
        newMessages.push(editedMessage);
        
        setMessages(newMessages);
        
        // 取消编辑状态
        setEditingMessageId(null);
        setEditingText('');
        
        // 重新发送消息以获取新的AI回复
        try {
          setIsLoading(true);
          const mappedHistory = newMessages.map(m => ({
            role: m.isUser ? 'user' : 'assistant',
            content: m.text
          }));
          const response = await apiCall(API_CONFIG.ENDPOINTS.CHAT, {
            message: editedMessage.text,
            history: mappedHistory,
            mode: llmMode === 'chat-plan' ? 'chat-only' : 'auto-search'
          });
          
          // 保存分析结果以供关键词面板使用
          if (response.hierarchical_keywords) {
            setCurrentAnalysis(response);
          }
          
          const aiMessage: Message = {
            id: Date.now().toString() + '_ai',
            text: response.response || response.message || '分析完成',
            isUser: false,
            timestamp: Date.now(),
            analysisResult: response.analysis_result,
            hierarchicalKeywords: response.analysis_result?.hierarchical_keywords
          };
          
          const finalMessages = [...newMessages, aiMessage];
          setMessages(finalMessages);
          saveChatHistory(finalMessages, response);
          
        } catch (error: any) {
          console.error('重新发送失败:', error);
          const errorMessage: Message = {
            id: Date.now().toString() + '_error',
            text: `抱歉，重新分析时出错：${error.message}`,
            isUser: false,
            timestamp: Date.now()
          };
          const errorMessages = [...newMessages, errorMessage];
          setMessages(errorMessages);
        } finally {
          setIsLoading(false);
        }
      }
    }
  };

  // 复制消息内容
  const copyMessage = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      // 可以添加一个临时的复制成功提示
    } catch (error) {
      console.error('复制失败:', error);
    }
  };

  return (
    <div className={`chat-interface ${className}`} style={{
      display: 'flex',
      height: '100vh',
      backgroundColor: theme === 'dark' ? '#000' : '#fefcf3',
      color: theme === 'dark' ? '#fff' : '#1f2937',
      overflow: 'hidden'
    }}>
        {/* 左侧My面板 */}
      {!isMyPanelCollapsed && (
        <div style={{
          width: isMobile ? '100vw' : `${myPanelWidth}px`,
          height: '100vh',
          borderRight: `1px solid ${theme === 'dark' ? '#333' : '#e5e5e5'}`,
          backgroundColor: theme === 'dark' ? '#0a0a0a' : '#fefcf3',
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
            borderBottom: `1px solid ${theme === 'dark' ? '#333' : '#e5e5e5'}`,
            backgroundColor: theme === 'dark' ? '#111' : '#f5f3ea'
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
                color: theme === 'dark' ? '#fff' : '#1f2937'
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
                    console.log('🔄 清除当前用户的聊天记录')
                    UserStorage.removeUserData(CHAT_STORAGE_KEY);
                    UserStorage.removeUserData(CHAT_ANALYSIS_KEY);
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
                    borderRadius: '12px',
                    border: '1px solid #10b981',
                    backgroundColor: theme === 'dark' ? 'rgba(16,185,129,0.1)' : 'rgba(16,185,129,0.05)',
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
                  color: theme === 'dark' ? '#999' : '#6b7280',
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
                  border: `1px solid ${theme === 'dark' ? '#666' : '#d1d5db'}`,
                  background: theme === 'dark' ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                  color: theme === 'dark' ? '#999' : '#6b7280',
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
                  backgroundColor: filter === 'search' ? '#3bb0e6' : (theme === 'dark' ? '#333' : '#e5e5e5'),
                  color: filter === 'search' ? '#fff' : (theme === 'dark' ? '#999' : '#6b7280'),
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
                  backgroundColor: filter === 'chat' ? '#3bb0e6' : (theme === 'dark' ? '#333' : '#e5e5e5'),
                  color: filter === 'chat' ? '#fff' : (theme === 'dark' ? '#999' : '#6b7280'),
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
                  color: theme === 'dark' ? '#999' : '#6b7280'
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
                      backgroundColor: selectedIds.includes(item.id) 
                        ? 'rgba(59,176,230,0.1)' 
                        : (theme === 'dark' ? '#1a1a1a' : '#ffffff'),
                      border: selectedIds.includes(item.id) 
                        ? '1px solid #3bb0e6' 
                        : `1px solid ${theme === 'dark' ? '#333' : '#e5e5e5'}`,
                      borderRadius: '6px',
                      padding: '8px',
                      cursor: 'pointer',
                      transition: 'all 0.2s'
                    }}
                    onMouseEnter={(e) => {
                      if (!selectedIds.includes(item.id)) {
                        e.currentTarget.style.backgroundColor = theme === 'dark' ? '#222' : '#ffffff';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!selectedIds.includes(item.id)) {
                        e.currentTarget.style.backgroundColor = theme === 'dark' ? '#1a1a1a' : '#ffffff';
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
                            color: theme === 'dark' ? '#fff' : '#374151',
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
                            e.currentTarget.style.color = theme === 'dark' ? '#999' : '#5a5a5a';
                            e.currentTarget.style.backgroundColor = theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.color = theme === 'dark' ? '#666' : '#9ca3af';
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
                                e.currentTarget.style.backgroundColor = theme === 'dark' ? '#333' : 'rgba(0,0,0,0.05)';
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
                                e.currentTarget.style.backgroundColor = theme === 'dark' ? '#333' : 'rgba(0,0,0,0.05)';
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
          
          {/* 个人主页入口 - 固定在My面板底部 */}
          <div style={{
            position: 'absolute',
            bottom: '0',
            left: '0',
            right: '0',
            backgroundColor: theme === 'dark' ? '#0a0a0a' : '#fefcf3',
            borderTop: `1px solid ${theme === 'dark' ? '#333' : '#e5e5e5'}`,
            padding: '12px 8px'
          }}>
            <div className="user-menu-container" style={{ position: 'relative' }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                borderRadius: '8px',
                backgroundColor: theme === 'dark' ? '#111' : '#f5f3ea',
                border: `1px solid ${theme === 'dark' ? '#333' : '#e5e5e5'}`,
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
              onClick={() => setShowUserMenu(!showUserMenu)}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = theme === 'dark' ? '#1a1a1a' : '#ede9d9';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = theme === 'dark' ? '#111' : '#f5f3ea';
              }}
              >
                {/* 用户头像 */}
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  border: 'none',
                  background: 'linear-gradient(135deg, #3bb0e6, #10b981)',
                  color: '#fff',
                  fontSize: '16px',
                  fontWeight: '900',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  boxShadow: '0 2px 6px rgba(0, 0, 0, 0.1)'
                }}>
                  {generateAvatar(localStorage.getItem('user_id') || '')}
                </div>
                
                {/* 用户信息 */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: '13px',
                    fontWeight: '500',
                    color: theme === 'dark' ? '#fff' : '#1f2937',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}>
                    {localStorage.getItem('user_id') || 'Unknown'}
                  </div>
                  <div style={{
                    fontSize: '11px',
                    color: theme === 'dark' ? '#a1a1aa' : '#6b7280'
                  }}>
                    Personal Profile
                  </div>
                </div>
                
                {/* 箭头图标 */}
                <div style={{
                  fontSize: '12px',
                  color: theme === 'dark' ? '#a1a1aa' : '#6b7280'
                }}>
                  →
                </div>
              </div>
              
              {/* 用户菜单 */}
              {showUserMenu && (
                <div style={{
                  position: 'absolute',
                  bottom: '60px',
                  left: '8px',
                  right: '8px',
                  background: theme === 'dark' ? '#1a1a1a' : '#f5f3ea',
                  border: `1px solid ${theme === 'dark' ? '#333' : '#e5e5e5'}`,
                  borderRadius: '8px',
                  boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)',
                  padding: '8px',
                  zIndex: 1000
                }}>
                  {/* 账号信息 */}
                  <div style={{
                    padding: '6px 10px',
                    borderBottom: `1px solid ${theme === 'dark' ? '#333' : '#e5e5e5'}`,
                    marginBottom: '6px'
                  }}>
                    <div style={{ fontSize: '11px', color: theme === 'dark' ? '#a1a1aa' : '#6b7280', marginBottom: '2px' }}>Account</div>
                    <div style={{ fontSize: '13px', color: theme === 'dark' ? '#fff' : '#1f2937', fontWeight: '500' }}>{localStorage.getItem('user_id')}</div>
                  </div>
                  
                  {/* 菜单项 */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <button
                      style={{
                        padding: '6px 10px',
                        background: 'transparent',
                        border: 'none',
                        color: theme === 'dark' ? '#a1a1aa' : '#6b7280',
                        fontSize: '13px',
                        textAlign: 'left',
                        cursor: 'not-allowed',
                        borderRadius: '4px',
                        opacity: 0.5,
                        height: '28px'
                      }}
                      disabled
                    >
                      Settings (Coming Soon)
                    </button>
                    <button
                      onClick={handleLogout}
                      style={{
                        padding: '6px 10px',
                        background: 'transparent',
                        border: 'none',
                        color: '#ef4444',
                        fontSize: '13px',
                        textAlign: 'left',
                        cursor: 'pointer',
                        borderRadius: '4px',
                        transition: 'background 0.2s',
                        height: '28px'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent'
                      }}
                    >
                      Log Out
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      
      {/* 中间聊天区域 */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: isMobile ? '100vw' : '320px',
        maxWidth: isMobile ? '100vw' : 'calc(100vw - 300px)' // 确保不超出屏幕
      }}>
        {/* 顶部标题栏 */}
        <div style={{
          padding: '16px 20px',
          borderBottom: `1px solid ${theme === 'dark' ? '#333' : '#e5e5e5'}`,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          position: 'relative',
          backgroundColor: theme === 'dark' ? '#000' : '#fefcf3'
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
              e.currentTarget.style.backgroundColor = theme === 'dark' ? 'rgba(161,161,170,0.1)' : 'rgba(0,0,0,0.05)';
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
          
          {/* 右侧按钮区域 - 已删除keywords折叠按钮 */}
          <div style={{ position: 'absolute', right: '20px', display: 'flex', gap: '8px' }}>
            {/* 关键词面板将根据宽度自动折叠，无需手动按钮 */}
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
                gap: '12px',
                position: 'relative'
              }}
              className={`message-container ${message.isUser ? 'user-message' : 'ai-message'}`}
            >
              {/* 头像 */}
              {!message.isUser && (
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  backgroundColor: '#3bb0e6',
                  color: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '20px',
                  fontWeight: '900',
                  flexShrink: 0,
                  letterSpacing: '-1px'
                }}>
                  V
                </div>
              )}

              {/* 消息气泡容器 */}
              <div style={{
                maxWidth: '75%',
                minWidth: '120px',
                position: 'relative',
                display: 'flex',
                flexDirection: 'column'
              }}>
                {/* 消息气泡 */}
                <div style={{
                  backgroundColor: message.isUser ? '#3bb0e6' : (theme === 'dark' ? '#1a1a1a' : '#f7f5eb'),
                  color: message.isUser ? '#fff' : (theme === 'dark' ? '#e5e5e5' : '#1f2937'),
                  padding: '12px 16px',
                  borderRadius: message.isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                  fontSize: '14px',
                  lineHeight: '1.6',
                  whiteSpace: message.isUser ? 'pre-wrap' : 'normal',
                  border: message.isUser ? 'none' : `1px solid ${theme === 'dark' ? '#333' : '#e5e5e5'}`,
                  position: 'relative'
                }}>
                  {message.isUser ? (
                    editingMessageId === message.id ? (
                      // 编辑模式
                      <div>
                        <textarea
                          value={editingText}
                          onChange={(e) => setEditingText(e.target.value)}
                          style={{
                            width: '100%',
                            minHeight: '60px',
                            padding: '8px',
                            border: 'none',
                            borderRadius: '6px',
                            backgroundColor: 'rgba(255,255,255,0.9)',
                            color: '#1f2937',
                            fontSize: '14px',
                            fontFamily: 'inherit',
                            resize: 'vertical',
                            outline: 'none'
                          }}
                          autoFocus
                        />
                        <div style={{
                          display: 'flex',
                          gap: '8px',
                          marginTop: '8px',
                          justifyContent: 'flex-end'
                        }}>
                          <button
                            onClick={cancelEdit}
                            style={{
                              padding: '4px 12px',
                              fontSize: '12px',
                              border: '1px solid rgba(255,255,255,0.3)',
                              borderRadius: '4px',
                              backgroundColor: 'transparent',
                              color: '#fff',
                              cursor: 'pointer'
                            }}
                          >
                            取消
                          </button>
                          <button
                            onClick={saveEdit}
                            style={{
                              padding: '4px 12px',
                              fontSize: '12px',
                              border: 'none',
                              borderRadius: '4px',
                              backgroundColor: 'rgba(255,255,255,0.2)',
                              color: '#fff',
                              cursor: 'pointer'
                            }}
                          >
                            保存
                          </button>
                        </div>
                      </div>
                    ) : (
                      // 正常显示模式
                      <div>{message.text}</div>
                    )
                  ) : (
                  <div style={{ position: 'relative' }}>
                    <ReactMarkdown
                      components={{
                        // 自定义组件样式，适配主题
                        h1: ({ children }) => <h1 style={{ color: theme === 'dark' ? '#e5e5e5' : '#1f2937', fontSize: '18px', marginBottom: '12px' }}>{children}</h1>,
                        h2: ({ children }) => <h2 style={{ color: theme === 'dark' ? '#e5e5e5' : '#1f2937', fontSize: '16px', marginBottom: '10px' }}>{children}</h2>,
                        h3: ({ children }) => <h3 style={{ color: theme === 'dark' ? '#e5e5e5' : '#1f2937', fontSize: '15px', marginBottom: '8px' }}>{children}</h3>,
                        p: ({ children }) => <p style={{ color: theme === 'dark' ? '#e5e5e5' : '#374151', marginBottom: '8px', lineHeight: '1.6' }}>{children}</p>,
                        strong: ({ children }) => <strong style={{ color: theme === 'dark' ? '#fff' : '#111827', fontWeight: '600' }}>{children}</strong>,
                        em: ({ children }) => <em style={{ color: theme === 'dark' ? '#e5e5e5' : '#374151', fontStyle: 'italic' }}>{children}</em>,
                        ul: ({ children }) => <ul style={{ color: theme === 'dark' ? '#e5e5e5' : '#374151', paddingLeft: '20px', marginBottom: '8px' }}>{children}</ul>,
                        ol: ({ children }) => <ol style={{ color: theme === 'dark' ? '#e5e5e5' : '#374151', paddingLeft: '20px', marginBottom: '8px' }}>{children}</ol>,
                        li: ({ children }) => <li style={{ color: theme === 'dark' ? '#e5e5e5' : '#374151', marginBottom: '4px' }}>{children}</li>,
                        code: ({ children }) => (
                          <code style={{
                            backgroundColor: theme === 'dark' ? '#333' : '#ebe7d6',
                            color: theme === 'dark' ? '#fff' : '#1f2937',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            fontSize: '13px',
                            fontFamily: 'monospace'
                          }}>{children}</code>
                        ),
                        pre: ({ children }) => (
                          <pre style={{
                            backgroundColor: theme === 'dark' ? '#333' : '#ebe7d6',
                            color: theme === 'dark' ? '#fff' : '#1f2937',
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
                            color: theme === 'dark' ? '#ccc' : '#6b7280',
                            fontStyle: 'italic'
                          }}>{children}</blockquote>
                        )
                    }}
                  >
                    {message.text}
                  </ReactMarkdown>
                  </div>
                )}

                {/* 用户消息的Edit按钮 - 左下角 */}
                {message.isUser && editingMessageId !== message.id && (
                  <button
                    className="hover-button-edit"
                    onClick={() => startEditMessage(message)}
                    style={{
                      position: 'absolute',
                      bottom: '-6px',
                      left: '8px',
                      padding: '4px 8px',
                      borderRadius: '8px',
                      border: 'none',
                      backgroundColor: theme === 'dark' ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                      color: theme === 'dark' ? '#fff' : '#1f2937',
                      cursor: 'pointer',
                      fontSize: '11px',
                      fontWeight: '600',
                      opacity: 0,
                      transition: 'all 0.2s ease',
                      zIndex: 10,
                      boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                      backdropFilter: 'blur(4px)'
                    }}
                    title="编辑消息"
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = theme === 'dark' ? 'rgba(0,0,0,0.9)' : 'rgba(255,255,255,1)';
                      e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.15)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = theme === 'dark' ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)';
                      e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
                    }}
                  >
                    Edit
                  </button>
                )}

                {/* AI消息的操作按钮 - 右下角 */}
                {!message.isUser && (
                  <div style={{
                    position: 'absolute',
                    bottom: '-6px',
                    right: '8px',
                    display: 'flex',
                    gap: '4px'
                  }}>
                    {/* Keywords 按钮：加载该消息的历史关键词到右侧云图 */}
                    {(message.hierarchicalKeywords || message.searchMetadata?.analysisResult?.hierarchical_keywords) && (
                      <button
                        className="hover-button-keywords"
                        onClick={() => handleShowKeywords(message)}
                        style={{
                          padding: '4px 8px',
                          borderRadius: '8px',
                          border: 'none',
                          backgroundColor: theme === 'dark' ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                          color: theme === 'dark' ? '#fff' : '#1f2937',
                          cursor: 'pointer',
                          fontSize: '11px',
                          fontWeight: '600',
                          opacity: 0,
                          transition: 'all 0.2s ease',
                          zIndex: 10,
                          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                          backdropFilter: 'blur(4px)'
                        }}
                        title="加载该回复的历史关键词"
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = theme === 'dark' ? 'rgba(0,0,0,0.9)' : 'rgba(255,255,255,1)';
                          e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.15)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = theme === 'dark' ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)';
                          e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
                        }}
                      >
                        Keywords
                      </button>
                    )}
                    {/* View Report按钮 - 仅在auto-search模式且有搜索结果时显示 */}
                    {(() => {
                      const hasSearchResults = message.searchResults && message.searchResults.length > 0;
                      const shouldShow = llmMode === 'auto-search' && hasSearchResults;
                      
                      // 调试信息（仅在开发环境）
                      if (process.env.NODE_ENV === 'development' && !message.isUser) {
                        console.log(`View Report按钮显示检查 [${message.id}]:`, {
                          llmMode,
                          hasSearchResults,
                          searchResultsLength: message.searchResults?.length || 0,
                          shouldShow,
                          messageText: message.text.substring(0, 50) + '...'
                        });
                      }
                      
                      return shouldShow;
                    })() && (
                      <button
                        className="hover-button-report"
                        onClick={() => {
                          navigate('/report', {
                            state: {
                              papers: message.searchResults,
                              searchHistory: {
                                id: 'chat_search_' + message.id,
                                timestamp: message.timestamp,
                                originalQuery: message.searchMetadata?.originalQuery || '',
                                expandedKeywords: message.searchMetadata?.expandedKeywords || [],
                                papers: message.searchResults || [],
                                maxResults: message.searchMetadata?.maxResults || (message.searchResults?.length || 0),
                                domain: message.searchMetadata?.analysisResult?.domain || 'unknown'
                              },
                              expandedKeywords: message.searchMetadata?.expandedKeywords || [],
                              originalQuery: message.searchMetadata?.originalQuery || '',
                              maxResults: message.searchMetadata?.maxResults || (message.searchResults?.length || 0)
                            }
                          });
                        }}
                        style={{
                          padding: '4px 8px',
                          borderRadius: '8px',
                          border: 'none',
                          backgroundColor: '#10b981',
                          color: '#fff',
                          cursor: 'pointer',
                          fontSize: '11px',
                          fontWeight: '600',
                          opacity: 0,
                          transition: 'all 0.2s ease',
                          zIndex: 10,
                          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                          backdropFilter: 'blur(4px)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '2px'
                        }}
                        title={`查看文献报告 (${message.searchResults?.length || 0}篇)`}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = '#059669';
                          e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.15)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = '#10b981';
                          e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
                        }}
                      >
                        📋 Report
                      </button>
                    )}
                    
                    {/* Copy按钮 */}
                    <button
                      className="hover-button-copy"
                      onClick={() => copyMessage(message.text)}
                      style={{
                        padding: '4px 8px',
                        borderRadius: '8px',
                        border: 'none',
                        backgroundColor: theme === 'dark' ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                        color: theme === 'dark' ? '#fff' : '#1f2937',
                        cursor: 'pointer',
                        fontSize: '11px',
                        fontWeight: '600',
                        opacity: 0,
                        transition: 'all 0.2s ease',
                        zIndex: 10,
                        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                        backdropFilter: 'blur(4px)'
                      }}
                      title="复制消息"
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = theme === 'dark' ? 'rgba(0,0,0,0.9)' : 'rgba(255,255,255,1)';
                        e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.15)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = theme === 'dark' ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)';
                        e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
                      }}
                    >
                      Copy
                    </button>
                  </div>
                )}
                
                

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
              </div>

            </div>
          ))}


          <div ref={messagesEndRef} />
        </div>

        {/* 当上下文超过阈值时的引导提示 */}
        {isContextOverloaded && (
          <div style={{
            margin: '8px 20px 0 20px',
            padding: '10px 12px',
            border: '1px solid #ef4444',
            borderRadius: 8,
            background: theme === 'dark' ? 'rgba(239,68,68,0.08)' : 'rgba(239,68,68,0.08)',
            color: theme === 'dark' ? '#fecaca' : '#b91c1c',
            fontSize: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12
          }}>
            <div>
              ⚠️ 当前对话已超过 4000 tokens，建议开启新话题以避免上下文压力。<br/>
              ⚠️ Context exceeds 4k tokens. Consider starting a new topic to reduce context pressure.
            </div>
            <button
              onClick={handleStartNewTopic}
              style={{
                padding: '6px 10px',
                borderRadius: 6,
                border: '1px solid #ef4444',
                background: theme === 'dark' ? 'rgba(239,68,68,0.12)' : '#fee2e2',
                color: theme === 'dark' ? '#fecaca' : '#b91c1c',
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: 600
              }}
            >
              Start new topic
            </button>
          </div>
        )}

        {/* 输入区域 */}
        <div style={{
          padding: '16px 20px',
          borderTop: `1px solid ${theme === 'dark' ? '#333' : '#e5e5e5'}`,
          backgroundColor: theme === 'dark' ? '#0a0a0a' : '#fefcf3'
        }}>
          <div style={{
            position: 'relative',
            display: 'flex',
            alignItems: 'flex-end'
          }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="输入您的学术问题或研究主题 / Enter academic/research interests..."
                disabled={isStreaming}
                style={{
                  width: '100%',
                  padding: '12px 60px 12px 16px',
                  borderRadius: '12px',
                  border: `1px solid ${theme === 'dark' ? '#333' : '#d1d5db'}`,
                  backgroundColor: theme === 'dark' ? '#1a1a1a' : '#ffffff',
                  color: theme === 'dark' ? '#fff' : '#1f2937',
                  fontSize: '14px',
                  fontStyle: 'italic',
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
              
              {/* 发送按钮放在输入框内部 */}
              <button
                onClick={handleSendMessage}
                disabled={isStreaming || !inputMessage.trim()}
                style={{
                  position: 'absolute',
                  right: '8px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  padding: '0',
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: inputMessage.trim() && !isStreaming ? '#3bb0e6' : '#666',
                  color: '#fff',
                  cursor: inputMessage.trim() && !isStreaming ? 'pointer' : 'not-allowed',
                  fontSize: '16px',
                  fontWeight: '900',
                  transition: 'all 0.2s',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
                title={isStreaming ? '正在流式传输...' : '发送消息'}
              >
                {isStreaming ? (
                  <span className="streaming-indicator">⟲</span>
                ) : '↑'}
              </button>
            </div>
          </div>
          
          <div style={{
            marginTop: '8px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            {/* LLM模式提示和快捷键 */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              fontSize: '11px',
              color: theme === 'dark' ? '#666' : '#9ca3af'
            }}>
              <span>
                Mode: <span style={{ 
                  color: llmMode === 'auto-search' ? '#10b981' : '#3bb0e6',
                  fontWeight: '600'
                }}>
                  {llmMode === 'auto-search' ? 'Auto-search' : 'Chat & Plan'}
                </span>
              </span>
              <span>Shift + Tab to cycle</span>
            </div>
            
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
            borderLeft: `1px solid ${theme === 'dark' ? '#333' : '#e5e5e5'}`,
            backgroundColor: theme === 'dark' ? '#0a0a0a' : '#fefcf3',
            position: 'relative',
            transition: isResizing ? 'none' : 'width 0.3s ease',
            display: 'flex',
            flexDirection: 'column'
          }}>
            {/* 关键词云面板头部 */}
            <div style={{
              padding: '12px 16px',
              borderBottom: `1px solid ${theme === 'dark' ? '#333' : '#e5e5e5'}`,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backgroundColor: theme === 'dark' ? '#0a0a0a' : '#f0f0f0'
            }}>
              <h3 style={{ 
                margin: 0, 
                fontSize: '14px', 
                fontWeight: '600',
                color: theme === 'dark' ? '#fff' : '#1f2937'
              }}>
                Keywords & Search
              </h3>
              
              {/* 主题切换双键开关 */}
              <button
                onClick={toggleTheme}
                style={{
                  width: '52px',
                  height: '24px',
                  borderRadius: '12px',
                  border: 'none',
                  backgroundColor: theme === 'dark' ? '#3bb0e6' : '#e5e5e5',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  padding: '2px',
                  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                  position: 'relative'
                }}
                title={theme === 'dark' ? '切换到白天模式' : '切换到夜间模式'}
              >
                {/* 滑动圆点 */}
                <div
                  style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    backgroundColor: '#ffffff',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transform: theme === 'dark' ? 'translateX(28px)' : 'translateX(0px)',
                    transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    fontSize: '10px'
                  }}
                >
                  {/* 简洁的图标 */}
                  {theme === 'dark' ? (
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="4" stroke="#3bb0e6" strokeWidth="2"/>
                      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 6.34L4.93 4.93M19.07 19.07l-1.41-1.41" stroke="#3bb0e6" strokeWidth="1.5"/>
                    </svg>
                  ) : (
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="#666" strokeWidth="2" fill="#666"/>
                    </svg>
                  )}
                </div>
              </button>
            </div>
            
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <KeywordCloudWidget 
                hierarchicalKeywords={currentAnalysis?.hierarchical_keywords || null}
                originalQuery=""
                isDraggable={true}
                theme={theme}
              />
            </div>
          </div>
        </>
      )}
      

      {/* 动画样式和悬停效果 */}
      <style>
        {`
          @keyframes pulse {
            0%, 100% { opacity: 0.4; transform: scale(0.8); }
            50% { opacity: 1; transform: scale(1.2); }
          }
          
          .message-container:hover .hover-button-edit {
            opacity: 1 !important;
          }
          
          .message-container:hover .hover-button-copy {
            opacity: 1 !important;
          }
          
          .message-container:hover .hover-button-report {
            opacity: 1 !important;
          }
          
          .user-message:hover .hover-button-edit {
            opacity: 1 !important;
          }
          
          .ai-message:hover .hover-button-copy {
            opacity: 1 !important;
          }
          
          .ai-message:hover .hover-button-report {
            opacity: 1 !important;
          }
          
          /* 响应式设计 */
          @media (max-width: 768px) {
            .chat-interface {
              flex-direction: column !important;
            }
            
            .message-container {
              margin: 0 8px !important;
            }
            
            .message-container .hover-button-edit,
            .message-container .hover-button-copy,
            .message-container .hover-button-report {
              opacity: 1 !important; /* 移动端始终显示按钮 */
            }
          }
        `}
      </style>
    </div>
  );
};

export default ChatInterface;