import React, { useState, useEffect } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import './App.css'
import { registerUser, logUserAction } from './auth';
import AdminDashboard from './AdminDashboard';
import ChatInterface from './ChatInterface';
import { api, APP_CONFIG, DEV_CONFIG } from './config';
import { useGlobal } from './contexts/GlobalContext';
import ThemeLanguageSwitcher from './components/ThemeLanguageSwitcher';

// 搜索历史管理
interface SearchHistory {
  id: string;
  timestamp: number;
  originalQuery: string;
  expandedKeywords: string[];
  papers: any[];
  maxResults: number;
}

// 聊天记录接口
interface ChatHistory {
  id: string;
  timestamp: number;
  title: string; // 聊天标题，取第一个用户消息
  messages: any[]; // 聊天消息数组
  lastActivity: number; // 最后活动时间
}

// 统一的历史记录接口
interface HistoryItem {
  id: string;
  timestamp: number;
  type: 'search' | 'chat';
  title: string;
  data: SearchHistory | ChatHistory;
}

const SEARCH_STORAGE_KEY = 'paper_god_search_history';
const CHAT_STORAGE_KEY = 'paper_god_chat_history';
const UNIFIED_HISTORY_KEY = 'paper_god_unified_history';

// 搜索历史管理
const saveSearchHistory = (history: SearchHistory) => {
  const existingHistory = JSON.parse(localStorage.getItem(SEARCH_STORAGE_KEY) || '[]');
  existingHistory.unshift(history);
  if (existingHistory.length > 50) {
    existingHistory.splice(50);
  }
  localStorage.setItem(SEARCH_STORAGE_KEY, JSON.stringify(existingHistory));
  
  // 同时保存到统一历史记录
  saveToUnifiedHistory({
    id: history.id,
    timestamp: history.timestamp,
    type: 'search',
    title: history.originalQuery,
    data: history
  });
};

const getSearchHistory = (): SearchHistory[] => {
  return JSON.parse(localStorage.getItem(SEARCH_STORAGE_KEY) || '[]');
};

const deleteSearchHistory = (ids: string[]) => {
  const existingHistory = getSearchHistory();
  const filteredHistory = existingHistory.filter(item => !ids.includes(item.id));
  localStorage.setItem(SEARCH_STORAGE_KEY, JSON.stringify(filteredHistory));
};

const clearAllSearchHistory = () => {
  localStorage.removeItem(SEARCH_STORAGE_KEY);
};

// 聊天历史管理
const saveChatHistory = (chat: ChatHistory) => {
  const existingHistory = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || '[]');
  const existingIndex = existingHistory.findIndex((item: ChatHistory) => item.id === chat.id);
  
  if (existingIndex >= 0) {
    existingHistory[existingIndex] = chat;
  } else {
    existingHistory.unshift(chat);
  }
  
  if (existingHistory.length > 50) {
    existingHistory.splice(50);
  }
  localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(existingHistory));
  
  // 同时保存到统一历史记录
  saveToUnifiedHistory({
    id: chat.id,
    timestamp: chat.lastActivity,
    type: 'chat',
    title: chat.title,
    data: chat
  });
};

const getChatHistory = (): ChatHistory[] => {
  return JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || '[]');
};

// 统一历史记录管理
const saveToUnifiedHistory = (item: HistoryItem) => {
  const existingHistory = JSON.parse(localStorage.getItem(UNIFIED_HISTORY_KEY) || '[]');
  const existingIndex = existingHistory.findIndex((h: HistoryItem) => h.id === item.id);
  
  if (existingIndex >= 0) {
    existingHistory[existingIndex] = item;
  } else {
    existingHistory.unshift(item);
  }
  
  // 按时间排序
  existingHistory.sort((a: HistoryItem, b: HistoryItem) => b.timestamp - a.timestamp);
  
  if (existingHistory.length > 100) {
    existingHistory.splice(100);
  }
  localStorage.setItem(UNIFIED_HISTORY_KEY, JSON.stringify(existingHistory));
};

const getUnifiedHistory = (): HistoryItem[] => {
  return JSON.parse(localStorage.getItem(UNIFIED_HISTORY_KEY) || '[]');
};

const deleteUnifiedHistory = (ids: string[]) => {
  const existingHistory = getUnifiedHistory();
  const filteredHistory = existingHistory.filter(item => !ids.includes(item.id));
  localStorage.setItem(UNIFIED_HISTORY_KEY, JSON.stringify(filteredHistory));
  
  // 同时删除对应的搜索和聊天历史
  const searchIds = ids.filter(id => {
    const item = existingHistory.find(h => h.id === id);
    return item?.type === 'search';
  });
  const chatIds = ids.filter(id => {
    const item = existingHistory.find(h => h.id === id);
    return item?.type === 'chat';
  });
  
  if (searchIds.length > 0) deleteSearchHistory(searchIds);
  if (chatIds.length > 0) {
    const chatHistory = getChatHistory();
    const filteredChatHistory = chatHistory.filter(item => !chatIds.includes(item.id));
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(filteredChatHistory));
  }
};

const clearAllHistory = () => {
  localStorage.removeItem(SEARCH_STORAGE_KEY);
  localStorage.removeItem(CHAT_STORAGE_KEY);
  localStorage.removeItem(UNIFIED_HISTORY_KEY);
};

// 简洁主题切换icon，仅用于报告页
function ReportThemeToggle({ theme, toggle }: { theme: string, toggle: () => void }) {
  return (
    <button
      onClick={toggle}
      style={{
        background: theme === 'dark' ? '#111' : '#3bb0e6',
        border: 'none',
        cursor: 'pointer',
        width: 60,
        height: 32,
        borderRadius: 20,
        display: 'flex',
        alignItems: 'center',
        justifyContent: theme === 'dark' ? 'flex-end' : 'flex-start',
        padding: 4,
        position: 'relative',
        transition: 'background 0.3s',
      }}
      aria-label="切换日夜模式"
      title={theme === 'dark' ? '切换为白天模式' : '切换为夜间模式'}
    >
      <span
        style={{
          width: 24,
          height: 24,
          borderRadius: '50%',
          background: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 1px 4px rgba(0,0,0,0.12)',
          fontSize: 18,
          transition: 'all 0.3s',
        }}
      >
        {theme === 'dark' ? (
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M15.5 13.5C13.5 15.5 10.5 15.5 8.5 13.5C6.5 11.5 6.5 8.5 8.5 6.5C10.5 4.5 13.5 4.5 15.5 6.5C17.5 8.5 17.5 11.5 15.5 13.5Z" stroke="#222" strokeWidth="1.5"/>
            <circle cx="14.5" cy="7.5" r="1" fill="#222"/>
            <circle cx="12.5" cy="10.5" r="0.5" fill="#222"/>
            <circle cx="16" cy="10" r="0.5" fill="#222"/>
          </svg>
        ) : (
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="10" cy="10" r="5" fill="#FFD600" stroke="#FFD600" strokeWidth="1.5"/>
            <g stroke="#FFD600" strokeWidth="1.2">
              <line x1="10" y1="2" x2="10" y2="4"/>
              <line x1="10" y1="16" x2="10" y2="18"/>
              <line x1="2" y1="10" x2="4" y2="10"/>
              <line x1="16" y1="10" x2="18" y2="10"/>
              <line x1="4.93" y1="4.93" x2="6.34" y2="6.34"/>
              <line x1="15.07" y1="15.07" x2="13.66" y2="13.66"/>
              <line x1="4.93" y1="15.07" x2="6.34" y2="13.66"/>
              <line x1="15.07" y1="4.93" x2="13.66" y2="6.34"/>
            </g>
          </svg>
        )}
      </span>
    </button>
  )
}

// 邀请码登录页
function InviteCodePage() {
  const navigate = useNavigate()
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { t } = useGlobal()

  // 校验邀请码并注册用户
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!code.trim()) {
      setError(t('invite.error.required'))
      return
    }
    setLoading(true)
    
    try {
      const result = await registerUser(code.trim())
      if (result.success && result.userData) {
        localStorage.setItem('invite_logged_in', '1')
        localStorage.setItem('user_id', result.userData.id)
        setError('')
        setLoading(false)
        navigate('/')
      } else {
        setError(result.error || t('invite.error.register'))
        setLoading(false)
      }
    } catch (error) {
      setError(t('invite.error.network'))
      setLoading(false)
    }
  }

  return (
    <div className="invite-page" style={{ minHeight: '100vh', background: '#000', color: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: 'rgba(30,30,30,0.98)', borderRadius: 18, padding: '48px 32px', boxShadow: '0 4px 32px rgba(0,0,0,0.18)', minWidth: 320, maxWidth: 360 }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 24 }}>
          <ThemeLanguageSwitcher />
        </div>
        <h2 style={{ fontWeight: 700, fontSize: '2rem', marginBottom: 24, textAlign: 'center' }}>{t('invite.title')}</h2>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <input
            type="text"
            value={code}
            onChange={e => setCode(e.target.value)}
            placeholder={t('invite.placeholder')}
            style={{ padding: '16px', borderRadius: 10, border: 'none', fontSize: 18, background: '#18181b', color: '#fff', textAlign: 'center', outline: 'none', marginBottom: 8 }}
            autoFocus
            disabled={loading}
          />
          {error && <div style={{ color: '#ff4d4f', marginBottom: 8, textAlign: 'center' }}>{error}</div>}
          <button type="submit" className="btn btn-primary" style={{ width: '100%', fontSize: 18 }} disabled={loading}>{loading ? t('invite.verifying') : t('invite.submit')}</button>
        </form>
      </div>
    </div>
  )
}

// 首页组件
function HomePage() {
  const [input, setInput] = useState('')
  const [currentSlide, setCurrentSlide] = useState(0)
  const navigate = useNavigate()
  // const { t } = useGlobal() - not currently needed

  // 3D轮播图片
  const carouselImages = [
    '/img1.jpg',
    '/img2.jpg',
    '/img3.jpg',
    '/img4.jpg',
    '/img5.jpg',
  ]

  // 3D轮播动画
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentSlide(prev => (prev + 1) % carouselImages.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  // 检查登录状态
  const isLoggedIn = localStorage.getItem('invite_logged_in') === '1'
  const userId = localStorage.getItem('user_id')
  const hasValidSession = isLoggedIn && userId

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!hasValidSession) {
      navigate('/invite')
      return
    }
    if (input.trim()) {
      navigate('/conversation', { state: { input } })
    }
  }

  return (
    <div className="homepage">
      {/* 页眉 */}
      <header className="header">
        <div className="logo">Veritex</div>
        <nav className="nav">
          <ul>
            <li><a href="/products">Products</a></li>
            <li><a href="/features">Features</a></li>
            <li><a href="#">Support</a></li>
          </ul>
        </nav>
        <div className="header-right">
          {hasValidSession ? (
            <>
              <button 
                className="btn btn-primary" 
                onClick={() => navigate('/my')}
                style={{ marginRight: 8 }}
              >
                My
              </button>
            </>
          ) : null}
          <button className="btn btn-primary" onClick={() => navigate('/invite')}>Start free trial</button>
        </div>
      </header>
      {/* 主体内容整体左移 */}
      <main className="main" style={{ justifyContent: 'flex-start', paddingLeft: '7vw' }}>
        <section className="hero">
          <h1 className="hero-title">Smart Academic Literature Search & Management Platform</h1>
          <p className="hero-desc">
            Veritex 依托大模型与智能算法，支持关键词扩展、批量论文检索、摘要智能提取与报告导出，帮你快速定位当前的研究进展。
          </p>
          
          
          <form className="hero-form" onSubmit={handleSubmit}>
            <input
              type="text"
              className="input"
              placeholder={hasValidSession ? "请输入关键词或学术问题..." : "请先获取内测邀请码"}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={!hasValidSession}
            />
            <div style={{ display: 'flex', gap: '12px' }}>
              <button type="submit" className="btn btn-secondary">
                {hasValidSession ? '🔍 Search & Chat' : 'Get Beta Code'}
              </button>
            </div>
          </form>
          
        </section>
        {/* 3D圆柱图片轮播 */}
        <div className="carousel-3d">
          <div className="carousel-3d-track" style={{ transform: `rotateY(${-72 * currentSlide}deg)` }}>
            {carouselImages.map((img, idx) => {
              const angle = (360 / carouselImages.length) * idx
              const isActive = idx === currentSlide
              return (
                <img
                  key={idx}
                  src={img}
                  alt={`carousel ${idx + 1}`}
                  className="carousel-3d-img"
                  style={{
                    transform: `translate(-50%, -50%) rotateY(${angle}deg) translateZ(220px) scale(${isActive ? 1.2 : 1})`,
                    opacity: isActive ? 1 : 0.5,
                    zIndex: isActive ? 2 : 1
                  }}
                />
              )
            })}
          </div>
        </div>
      </main>
    </div>
  )
}


// 报告页组件
function ReportPage() {
  const navigate = useNavigate()
  const { theme, t, toggleTheme } = useGlobal()
  const location = useLocation()
  const [papers] = useState(location.state?.papers || [])
  const [expandedKeywords] = useState(location.state?.expandedKeywords || [])
  const [originalQuery] = useState(location.state?.originalQuery || '')
  const [maxResults] = useState(location.state?.maxResults || 20)
  const [expandedIdx, setExpandedIdx] = useState<{[key:number]: boolean}>({})
  const MAX_ABSTRACT = APP_CONFIG.ABSTRACT_PREVIEW_LENGTH
  const toggleAbstract = (idx: number) => setExpandedIdx(e => ({...e, [idx]: !e[idx]}))

  const handleExport = () => {
    const csvContent = [
      [t('report.table.title'), t('report.table.authors'), t('report.table.year'), t('report.table.abstract'), t('report.table.link')],
      ...papers.map((p: any) => [p.title, p.authors, p.year, p.abstract, p.url])
    ].map(row => row.map((cell: any) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n')
    const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = '文献报告.csv'
    link.click()
  }

  const handleBackToChat = () => {
    // 返回聊天页面，不传递状态以保持现有聊天记录
    navigate('/conversation')
  }


  return (
    <div className={`report-page ${theme === 'light' ? 'light' : 'dark'} page-enter page-enter-active`}> 
      <div className="report-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button 
            onClick={handleBackToChat}
            style={{
              padding: '8px 16px',
              borderRadius: 6,
              border: '1px solid #666',
              background: 'transparent',
              color: theme === 'dark' ? '#fff' : '#333',
              cursor: 'pointer',
              fontSize: 14,
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            {t('report.back')}
          </button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {/* 导出和主题切换 */}
          <button onClick={handleExport} className="export-button">{t('report.export')}</button>
          <ReportThemeToggle theme={theme} toggle={toggleTheme} />
        </div>
      </div>
      
      {/* 仅保留表格视图，移除关系图 */}
      <div className="view-switch-container">
        <div className="view-content view-enter view-enter-active">
          <div className="report-table-wrapper">
            <table className="report-table">
              <thead>
                <tr>
                  <th className="col-title">{t('report.table.title')}</th>
                  <th className="col-authors">{t('report.table.authors')}</th>
                  <th className="col-year">{t('report.table.year')}</th>
                  <th className="col-abstract">{t('report.table.abstract')}</th>
                  <th className="col-link">{t('report.table.link')}</th>
                </tr>
              </thead>
              <tbody>
                {papers.map((paper: any, idx: number) => {
                  const abstract = paper.abstract || ''
                  const isLong = abstract.length > MAX_ABSTRACT
                  const showAll = expandedIdx[idx]
                  return (
                    <tr key={idx} style={{ animationDelay: `${idx * 0.05}s` }}>
                      <td className="col-title">
                        <div className="title-content">{paper.title}</div>
                      </td>
                      <td className="col-authors">
                        <div className="authors-content">{paper.authors}</div>
                      </td>
                      <td className="col-year">
                        <div className="year-content">{paper.year}</div>
                      </td>
                      <td className="col-abstract">
                        <div className="abstract-content">
                          {isLong && !showAll
                            ? abstract.slice(0, MAX_ABSTRACT) + '...'
                            : abstract}
                          {isLong && (
                            <button className="abstract-toggle" onClick={() => toggleAbstract(idx)}>
                              {showAll ? t('report.abstract.less') : t('report.abstract.more')}
                            </button>
                          )}
                        </div>
                      </td>
                      <td className="col-link">
                        <a href={paper.url} target="_blank" rel="noopener noreferrer" className="link-button">
                          {t('common.view')}
                        </a>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

// Elicit风格研究页面
function ElicitPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [query] = useState(location.state?.query || '')

  // 检查登录状态
  useEffect(() => {
    const isLoggedIn = localStorage.getItem('invite_logged_in') === '1'
    const userId = localStorage.getItem('user_id')
    
    if (!isLoggedIn || !userId) {
      localStorage.removeItem('invite_logged_in')
      localStorage.removeItem('user_id')
      navigate('/invite')
    }
  }, [navigate])

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: '#000', 
      color: '#fff', 
      padding: '20px'
    }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <h2 style={{ fontSize: 28, color: '#3bb0e6' }}>
          ⚡ Elicit风格研究分析
        </h2>
        <p style={{ color: '#a1a1aa' }}>
          查询: "{query}" - 功能开发中，敬请期待！
        </p>
      </div>
    </div>
  )
}

// Products页面
function ProductsPage() {
  return (
    <div className="products-page" style={{ minHeight: '100vh', background: '#000', color: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-start', paddingTop: 40 }}>
      <h1 style={{ fontSize: '3rem', fontWeight: 'bold', marginBottom: 0, marginTop: 0, letterSpacing: 1, lineHeight: 1.1, textAlign: 'center' }}>Products</h1>
      <div style={{ maxWidth: 1100, width: '100%', margin: '0 auto', marginTop: 16, textAlign: 'center' }}>
        <h2 style={{ fontWeight: 700, fontSize: '1.5rem', margin: '32px 0 12px 0', color: '#fff' }}>
          Veritex - Smart Academic Literature Search & Management Platform
        </h2>
        <p style={{ color: '#a1a1aa', fontSize: '1.15rem', margin: '0 auto', maxWidth: 900, lineHeight: 1.7 }}>
          Veritex is an AI-powered platform designed to streamline your academic research. Leveraging large language models and intelligent algorithms, it supports keyword expansion, batch paper retrieval, abstract extraction, and report generation. Quickly identify the latest research trends with precision and efficiency.
        </p>
        <div style={{ margin: '40px 0 0 0', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div style={{ fontWeight: 700, fontSize: '1.3rem', marginBottom: 18, color: '#fff' }}>Key Highlights:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 60, marginBottom: 24 }}>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, textAlign: 'left', minWidth: 320 }}>
              <li style={{ marginBottom: 18, color: '#fff', fontSize: '1.08rem' }}><span style={{ color: '#4a90e2', fontSize: 18, marginRight: 8 }}>•</span>Intelligent keyword expansion</li>
              <li style={{ marginBottom: 18, color: '#fff', fontSize: '1.08rem' }}><span style={{ color: '#4a90e2', fontSize: 18, marginRight: 8 }}>•</span>One-click report export</li>
            </ul>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, textAlign: 'left', minWidth: 320 }}>
              <li style={{ marginBottom: 18, color: '#fff', fontSize: '1.08rem' }}><span style={{ color: '#4a90e2', fontSize: 18, marginRight: 8 }}>•</span>Customizable search parameters</li>
              <li style={{ marginBottom: 18, color: '#fff', fontSize: '1.08rem' }}><span style={{ color: '#4a90e2', fontSize: 18, marginRight: 8 }}>•</span>Seamless integration with academic databases</li>
            </ul>
          </div>
          <div style={{ color: '#a1a1aa', fontSize: '1.15rem', margin: '24px 0 0 0', fontWeight: 400 }}>Start exploring now and find your papers faster!</div>
        </div>
        <div style={{ marginTop: 70, color: '#fff', fontSize: '1.1rem', textAlign: 'center', fontWeight: 600 }}>
          <span style={{ color: '#a1a1aa', fontWeight: 700, fontSize: '1.08rem' }}>开发者寄语 / About the Developer</span>
          <div style={{ margin: '18px auto 0 auto', maxWidth: 900, color: '#a1a1aa', fontWeight: 400, fontSize: '1.05rem', lineHeight: 1.9 }}>
            这是一个充满激情和野心的AI项目。作为一名STEM的研究生，我始终希望我的研究能够基于对科学问题的解决、对现实应用的考量以及对基础科学的纯粹追求而不是人云亦云，这也是我开发这款应用的初衷。在AI平权的时代，我们应有更多机会去接近真理，建立自己的思考体系，也相信是每一位用户对AI的共同愿景。项目初期将全面开放，永久免费。我们会倾听每一位用户的声音，迅速优化产品，不断迭代功能。诚邀你与我们一起，见证它的成长。
          </div>
          <div style={{ fontStyle: 'italic', color: '#a1a1aa', marginTop: 18, fontSize: '1.05rem' }}>
            Ultimately it comes down to taste, it comes down to taste.....
          </div>
          <div style={{ marginTop: 24, color: '#fff', fontWeight: 500, fontSize: '1.08rem' }}>
            欢迎联系与合作：<br />
            Email: <a href="mailto:yhr180414@163.com" style={{ color: '#4a90e2', textDecoration: 'underline' }}>yhr180414@163.com</a><br />
            小红书ID：Rogerrrr
          </div>
        </div>
      </div>
    </div>
  )
}

// Features页面
function FeaturesPage() {
  return (
    <div className="features-page">
      <h1>Features</h1>
      <p>功能特性页面 - 请在这里添加您的功能特性信息</p>
    </div>
  )
}

// "我的"页面 - 历史记录管理  
function MyPage() {
  const navigate = useNavigate()
  const [unifiedHistory, setUnifiedHistory] = useState<HistoryItem[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [selectAll, setSelectAll] = useState(false)
  const [filter, setFilter] = useState<'all' | 'search' | 'chat'>('all')
  // useGlobal hook available but not currently needed

  // 检查登录状态
  useEffect(() => {
    const isLoggedIn = localStorage.getItem('invite_logged_in') === '1'
    const userId = localStorage.getItem('user_id')
    
    if (!isLoggedIn || !userId) {
      localStorage.removeItem('invite_logged_in')
      localStorage.removeItem('user_id')
      navigate('/invite')
      return
    }
    
    // 加载历史记录
    loadHistory()
  }, [navigate])

  const loadHistory = () => {
    const history = getUnifiedHistory()
    setUnifiedHistory(history)
  }

  const filteredHistory = filter === 'all' ? unifiedHistory : unifiedHistory.filter(item => item.type === filter)

  const handleSelectAll = () => {
    if (selectAll) {
      setSelectedIds([])
    } else {
      setSelectedIds(filteredHistory.map(item => item.id))
    }
    setSelectAll(!selectAll)
  }

  const handleSelectItem = (id: string) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter(sid => sid !== id))
    } else {
      setSelectedIds([...selectedIds, id])
    }
  }

  const handleDeleteSelected = () => {
    if (selectedIds.length === 0) return
    
    if (confirm(`确定要删除选中的 ${selectedIds.length} 条记录吗？`)) {
      deleteUnifiedHistory(selectedIds)
      setSelectedIds([])
      setSelectAll(false)
      loadHistory()
    }
  }

  const handleClearAll = () => {
    if (confirm('确定要清空所有历史记录吗？此操作不可恢复。')) {
      clearAllHistory()
      setUnifiedHistory([])
      setSelectedIds([])
      setSelectAll(false)
    }
  }

  const handleViewItem = (item: HistoryItem) => {
    if (item.type === 'search') {
      const searchData = item.data as SearchHistory;
      // 直接查看历史报告
      navigate('/report', {
        state: {
          papers: searchData.papers,
          searchHistory: searchData,
          expandedKeywords: searchData.expandedKeywords,
          originalQuery: searchData.originalQuery,
          maxResults: searchData.maxResults
        }
      })
    } else if (item.type === 'chat') {
      // 恢复聊天记录并跳转
      const chatData = item.data as ChatHistory;
      // 先保存聊天记录到当前会话
      localStorage.setItem('veritex_chat_history', JSON.stringify(chatData.messages));
      navigate('/conversation');
    }
  }

  const handleReSearch = (item: HistoryItem) => {
    if (item.type === 'search') {
      const searchData = item.data as SearchHistory;
      navigate('/conversation', {
        state: {
          input: searchData.originalQuery,
          preserveChat: true
        }
      })
    } else if (item.type === 'chat') {
      const chatData = item.data as ChatHistory;
      // 恢复聊天记录
      localStorage.setItem('veritex_chat_history', JSON.stringify(chatData.messages));
      navigate('/conversation');
    }
  }

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    
    if (diffDays === 0) {
      return 'Today ' + date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    } else if (diffDays === 1) {
      return 'Yesterday ' + date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    } else if (diffDays < 7) {
      return `${diffDays} days ago`
    } else {
      return date.toLocaleDateString('en-US')
    }
  }

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: '#000', 
      color: '#fff', 
      padding: '20px'
    }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        {/* 页面头部 */}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          marginBottom: '24px',
          borderBottom: '1px solid var(--border-primary)',
          paddingBottom: '16px'
        }}>
          <div>
            <h2 style={{ fontSize: 28, color: 'var(--accent-primary)', margin: 0 }}>My History</h2>
            <p style={{ color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
              Total {filteredHistory.length} records ({filter})
              {selectedIds.length > 0 && ` · Selected ${selectedIds.length} items`}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            {/* 过滤器 */}
            <div style={{ display: 'flex', gap: 4, marginRight: 12 }}>
              {(['all', 'search', 'chat'] as const).map(filterType => (
                <button
                  key={filterType}
                  onClick={() => setFilter(filterType)}
                  style={{
                    padding: '4px 12px',
                    borderRadius: 4,
                    border: '1px solid var(--border-primary)',
                    background: filter === filterType ? 'var(--accent-primary)' : 'transparent',
                    color: filter === filterType ? '#fff' : 'var(--text-secondary)',
                    cursor: 'pointer',
                    fontSize: 12,
                    textTransform: 'capitalize'
                  }}
                >
                  {filterType}
                </button>
              ))}
            </div>
            <ThemeLanguageSwitcher className="my-page-switcher" />
            <button
              onClick={() => navigate('/')}
              style={{
                padding: '8px 16px',
                borderRadius: 6,
                border: '1px solid var(--border-primary)',
                background: 'transparent',
                color: 'var(--text-primary)',
                cursor: 'pointer',
                fontSize: 14
              }}
            >
              Home
            </button>
          </div>
        </div>

        {/* 操作栏 */}
        {filteredHistory.length > 0 && (
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            marginBottom: '20px',
            padding: '12px 16px',
            background: '#111',
            borderRadius: 8,
            border: '1px solid #333'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={selectAll}
                  onChange={handleSelectAll}
                  style={{ cursor: 'pointer' }}
                />
                Select All
              </label>
              <button
                onClick={handleDeleteSelected}
                disabled={selectedIds.length === 0}
                style={{
                  padding: '6px 12px',
                  borderRadius: 4,
                  border: 'none',
                  background: selectedIds.length > 0 ? '#dc3545' : '#666',
                  color: '#fff',
                  cursor: selectedIds.length > 0 ? 'pointer' : 'not-allowed',
                  fontSize: 12
                }}
              >
                Delete ({selectedIds.length})
              </button>
            </div>
            <button
              onClick={handleClearAll}
              style={{
                padding: '6px 12px',
                borderRadius: 4,
                border: '1px solid #dc3545',
                background: 'transparent',
                color: '#dc3545',
                cursor: 'pointer',
                fontSize: 12
              }}
            >
              Clear All
            </button>
          </div>
        )}

        {/* 历史记录列表 */}
        {filteredHistory.length === 0 ? (
          <div style={{ 
            textAlign: 'center', 
            padding: '60px 20px',
            color: '#666'
          }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>📚</div>
            <h3 style={{ margin: '0 0 8px 0' }}>No search history yet</h3>
            <p style={{ margin: 0 }}>Start your first literature search!</p>
            <button
              onClick={() => navigate('/')}
              style={{
                marginTop: 20,
                padding: '12px 24px',
                borderRadius: 8,
                border: 'none',
                background: '#3bb0e6',
                color: '#fff',
                cursor: 'pointer',
                fontSize: 16
              }}
            >
              Start Search
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {filteredHistory.map((item) => (
              <div
                key={item.id}
                style={{
                  padding: 20,
                  background: '#111',
                  borderRadius: 12,
                  border: selectedIds.includes(item.id) ? '2px solid #3bb0e6' : '1px solid #333',
                  transition: 'all 0.2s'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(item.id)}
                    onChange={() => handleSelectItem(item.id)}
                    style={{ marginTop: 4, cursor: 'pointer' }}
                  />
                  
                  <div style={{ flex: 1 }}>
                    {/* 记录信息 */}
                    <div style={{ marginBottom: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: 12,
                          fontSize: 11,
                          fontWeight: 600,
                          background: item.type === 'search' ? 'rgba(34,197,94,0.2)' : 'rgba(147,51,234,0.2)',
                          color: item.type === 'search' ? '#22c55e' : '#9333ea',
                          border: `1px solid ${item.type === 'search' ? 'rgba(34,197,94,0.3)' : 'rgba(147,51,234,0.3)'}`
                        }}>
                          {item.type === 'search' ? '🔍 SEARCH' : '💬 CHAT'}
                        </span>
                      </div>
                      <h4 style={{ 
                        margin: '0 0 8px 0', 
                        fontSize: 16, 
                        color: '#fff',
                        fontWeight: 600 
                      }}>
                        "{item.title}"
                      </h4>
                      <div style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: 16, 
                        fontSize: 14, 
                        color: '#a1a1aa' 
                      }}>
                        <span>{formatDate(item.timestamp)}</span>
                        <span>•</span>
                        {item.type === 'search' ? (
                          <>
                            <span>{(item.data as SearchHistory).papers.length} papers</span>
                            <span>•</span>
                            <span>Target: {(item.data as SearchHistory).maxResults}</span>
                          </>
                        ) : (
                          <>
                            <span>{(item.data as ChatHistory).messages.length} messages</span>
                            <span>•</span>
                            <span>Last: {formatDate((item.data as ChatHistory).lastActivity)}</span>
                          </>
                        )}
                      </div>
                    </div>

                    {/* 搜索记录的扩展关键词 */}
                    {item.type === 'search' && (
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>Expanded Keywords:</div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          {(item.data as SearchHistory).expandedKeywords.map((keyword, idx) => (
                            <span
                              key={idx}
                              style={{
                                padding: '2px 8px',
                                background: 'rgba(59,176,230,0.1)',
                                borderRadius: 12,
                                fontSize: 12,
                                color: 'var(--accent-primary)',
                                border: '1px solid rgba(59,176,230,0.2)'
                              }}
                            >
                              {keyword}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 聊天记录的消息预览 */}
                    {item.type === 'chat' && (
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>Recent Messages:</div>
                        <div style={{ 
                          maxHeight: 60, 
                          overflowY: 'auto',
                          fontSize: 13,
                          color: '#ccc',
                          lineHeight: 1.4
                        }}>
                          {(item.data as ChatHistory).messages.slice(-3).map((msg: any, idx: number) => (
                            <div key={idx} style={{ marginBottom: 4 }}>
                              <span style={{ color: msg.isUser ? '#3bb0e6' : '#a1a1aa' }}>
                                {msg.isUser ? 'You: ' : 'AI: '}
                              </span>
                              {msg.text.slice(0, 50)}{msg.text.length > 50 ? '...' : ''}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 操作按钮 */}
                    <div style={{ display: 'flex', gap: 12 }}>
                      <button
                        onClick={() => handleViewItem(item)}
                        style={{
                          padding: '6px 16px',
                          borderRadius: 6,
                          border: `1px solid ${item.type === 'search' ? '#22c55e' : '#9333ea'}`,
                          background: `rgba(${item.type === 'search' ? '34,197,94' : '147,51,234'},0.1)`,
                          color: item.type === 'search' ? '#22c55e' : '#9333ea',
                          cursor: 'pointer',
                          fontSize: 13
                        }}
                      >
                        {item.type === 'search' ? 'View Report' : 'Open Chat'}
                      </button>
                      <button
                        onClick={() => handleReSearch(item)}
                        style={{
                          padding: '6px 16px',
                          borderRadius: 6,
                          border: '1px solid #666',
                          background: 'transparent',
                          color: '#fff',
                          cursor: 'pointer',
                          fontSize: 13
                        }}
                      >
                        {item.type === 'search' ? 'Re-search' : 'Continue Chat'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/invite" element={<InviteCodePage />} />
      <Route path="/conversation" element={<ChatInterface />} />
      <Route path="/elicit" element={<ElicitPage />} />
      <Route path="/report" element={<ReportPage />} />
      <Route path="/my" element={<MyPage />} />
      <Route path="/products" element={<ProductsPage />} />
      <Route path="/features" element={<FeaturesPage />} />
      <Route path="/admin" element={<AdminDashboard />} />
      {/* 移除作者分析相关路由 */}
    </Routes>
  )
}

export default App
