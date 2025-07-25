import React, { useState, useEffect, createContext, useContext } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import './App.css'
import { supabase, registerUser, logUserAction } from './supabaseClient';
import AdminDashboard from './AdminDashboard';
import { api, APP_CONFIG, DEV_CONFIG } from './config';

// 搜索历史管理
interface SearchHistory {
  id: string;
  timestamp: number;
  originalQuery: string;
  expandedKeywords: string[];
  papers: any[];
  maxResults: number;
}

const STORAGE_KEY = 'paper_god_search_history';

const saveSearchHistory = (history: SearchHistory) => {
  const existingHistory = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  existingHistory.unshift(history); // 最新的在前面
  // 只保留最近50次搜索
  if (existingHistory.length > 50) {
    existingHistory.splice(50);
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(existingHistory));
};

const getSearchHistory = (): SearchHistory[] => {
  return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
};

const deleteSearchHistory = (ids: string[]) => {
  const existingHistory = getSearchHistory();
  const filteredHistory = existingHistory.filter(item => !ids.includes(item.id));
  localStorage.setItem(STORAGE_KEY, JSON.stringify(filteredHistory));
};

const clearAllSearchHistory = () => {
  localStorage.removeItem(STORAGE_KEY);
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

  // 校验邀请码并注册用户
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!code.trim()) {
      setError('请输入内测邀请码')
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
        setError(result.error || '注册失败')
        setLoading(false)
      }
    } catch (error) {
      setError('注册过程中出错')
      setLoading(false)
    }
  }

  return (
    <div className="invite-page" style={{ minHeight: '100vh', background: '#000', color: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: 'rgba(30,30,30,0.98)', borderRadius: 18, padding: '48px 32px', boxShadow: '0 4px 32px rgba(0,0,0,0.18)', minWidth: 320, maxWidth: 360 }}>
        <h2 style={{ fontWeight: 700, fontSize: '2rem', marginBottom: 24, textAlign: 'center' }}>填写内测邀请码</h2>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <input
            type="text"
            value={code}
            onChange={e => setCode(e.target.value)}
            placeholder="请输入6位内测码"
            style={{ padding: '16px', borderRadius: 10, border: 'none', fontSize: 18, background: '#18181b', color: '#fff', textAlign: 'center', outline: 'none', marginBottom: 8 }}
            autoFocus
            disabled={loading}
          />
          {error && <div style={{ color: '#ff4d4f', marginBottom: 8, textAlign: 'center' }}>{error}</div>}
          <button type="submit" className="btn btn-primary" style={{ width: '100%', fontSize: 18 }} disabled={loading}>{loading ? '校验中...' : '进入内测'}</button>
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
      navigate('/keywords', { state: { input } })
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
            <li><a href="#">Pricing</a></li>
            <li><a href="#">Support</a></li>
          </ul>
        </nav>
        <div className="header-right">
          {hasValidSession ? (
            <button 
              className="btn btn-primary" 
              onClick={() => navigate('/my')}
              style={{ marginRight: 8 }}
            >
              我的
            </button>
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
              placeholder={hasValidSession ? "请输入关键词(请放心,我会帮你自动拓展)." : "请先获取内测邀请码"}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={!hasValidSession}
            />
            <button type="submit" className="btn btn-secondary">
              {hasValidSession ? '🔍 开始搜索' : '获取内测邀请码'}
            </button>
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

// 关键词云页面组件
function KeywordCloudPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [input] = useState(location.state?.input || '')
  const [expanded, setExpanded] = useState<string[]>(location.state?.expandedKeywords ? [...location.state.expandedKeywords, ''] : [])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [maxResults, setMaxResults] = useState<number>(location.state?.maxResults || APP_CONFIG.DEFAULT_MAX_RESULTS)
  const [yearLow, setYearLow] = useState<string>('')
  const [yearHigh, setYearHigh] = useState<string>('')
  const [showLoading, setShowLoading] = useState(false)
  const [skipExpansion] = useState(location.state?.skipExpansion || false)
  

  // 检查登录状态，未登录强制跳转/invite
  useEffect(() => {
    const isLoggedIn = localStorage.getItem('invite_logged_in') === '1'
    const userId = localStorage.getItem('user_id')
    
    if (!isLoggedIn || !userId) {
      // 清除可能的无效状态
      localStorage.removeItem('invite_logged_in')
      localStorage.removeItem('user_id')
      navigate('/invite')
    }
    // eslint-disable-next-line
  }, [])

  // 自动扩展关键词
  useEffect(() => {
    if (input && !skipExpansion) {
      setShowLoading(true)
      handleExpand()
    }
    // eslint-disable-next-line
  }, [input])

  // 关键词扩展
  const handleExpand = async () => {
    if (localStorage.getItem('invite_logged_in') !== '1') {
      navigate('/invite')
      return
    }
    
    const userId = localStorage.getItem('user_id')
    if (!userId) {
      localStorage.removeItem('invite_logged_in')
      navigate('/invite')
      return
    }
    
    setError('')
    setLoading(true)
    setShowLoading(true)
    
    try {
      // 记录行为
      await logUserAction(userId, 'expand_keywords', input)
      
      // 使用配置化的API调用
      const maxKeywords = 5
      const data = await api.expandKeywords(input, maxKeywords)
      
      // 适配优化后端响应格式
      if (data.success && data.data) {
        const responseData = data.data
        
        // 调试日志
        if (DEV_CONFIG.ENABLE_DEBUG_LOGS) {
          console.log('[前端] 后端响应数据:', responseData)
          console.log('[前端] 扩展关键词:', responseData.expanded_keywords)
        }
        
        // 设置扩展的关键词
        const keywords = responseData.expanded_keywords || []
        // 添加一个空字符串用于新增输入
        const expandedWithEmpty = keywords.length > 0 ? [...keywords, ''] : ['']
        
        setExpanded(expandedWithEmpty)
      } else {
        // 兼容旧格式响应
        const keywords = data.expanded_terms || data.expanded_keywords || []
        const expandedWithEmpty = keywords.length > 0 ? [...keywords, ''] : ['']
        setExpanded(expandedWithEmpty)
        
        if (DEV_CONFIG.ENABLE_DEBUG_LOGS) {
          console.log('[前端] 使用兼容格式，关键词:', keywords)
        }
      }
    } catch (e: any) {
      setError(e.message || '扩展关键词失败')
    }
    setLoading(false)
    setShowLoading(false)
  }

  // 扩展结果可编辑
  const handleExpandedChange = (idx: number, value: string) => {
    let newExpanded = [...expanded]
    if (value.trim() === '') {
      newExpanded.splice(idx, 1)
    } else {
      newExpanded[idx] = value
    }
    if (newExpanded.length === 0 || newExpanded[newExpanded.length - 1].trim() !== '') {
      newExpanded.push('')
    }
    setExpanded(newExpanded)
  }

  const handleRemoveExpanded = (idx: number) => {
    setExpanded(expanded.filter((_, i) => i !== idx))
  }

  const handleAddExpanded = () => {
    setExpanded([...expanded, ''])
  }

  // 生成泡泡颜色
  const getBubbleColor = (idx: number) => {
    const hue = (idx * 47) % 360
    return `hsl(${hue}, 70%, 60%)`
  }

  // 开始检索
  const handleSearch = async () => {
    if (localStorage.getItem('invite_logged_in') !== '1') {
      navigate('/invite')
      return
    }
    
    const userId = localStorage.getItem('user_id')
    if (!userId) {
      // 如果没有用户ID，清除登录状态并跳转
      localStorage.removeItem('invite_logged_in')
      navigate('/invite')
      return
    }
    
    setError('')
    const validKeywords = expanded.filter(k => k.trim())
    if (validKeywords.length === 0) {
      setError('请至少输入一个关键词')
      return
    }
    
    setLoading(true)
    try {
      // 记录行为
      await logUserAction(userId, 'search_papers', validKeywords.join(','))
      
      // 构造查询字符串，适配优化后端格式
      const queryString = validKeywords.join(' OR ')
      
      // 使用配置化的API调用
      const data = await api.searchPapers(queryString, maxResults, false)
      
      // 适配优化后端响应格式
      const papers = data.success && data.data ? data.data.papers : (data.papers || [])
      
      // 保存搜索历史
      const searchHistory: SearchHistory = {
        id: Date.now().toString(),
        timestamp: Date.now(),
        originalQuery: input,
        expandedKeywords: validKeywords,
        papers: papers,
        maxResults: maxResults
      };
      saveSearchHistory(searchHistory);
      
      navigate('/report', { 
        state: { 
          papers,
          searchHistory,
          expandedKeywords: validKeywords,
          originalQuery: input,
          maxResults: maxResults
        } 
      })
    } catch (e: any) {
      setError(e.message || '检索论文失败')
    }
    setLoading(false)
  }

  return (
    <div className="keyword-cloud-page">
      <div className="cloud-header">
        <h2>Keyword Cloud</h2>
        <p>Edit your keywords, then start searching</p>
        
      </div>
      
      {error && <p className="error-message">错误: {error}</p>}
      
      {showLoading && <div className="loading-spinner">扩展关键词中...</div>}
      
      
      <div className="keyword-bubbles">
        {expanded.map((term, idx) => (
          <div
            key={idx}
            className="keyword-bubble"
            style={{
              backgroundColor: getBubbleColor(idx),
              animationDelay: `${idx * 0.1}s`
            }}
          >
            <input
              type="text"
              value={term}
              onChange={(e) => handleExpandedChange(idx, e.target.value)}
              placeholder="输入关键词"
              className="bubble-input"
              disabled={loading}
            />
            {expanded.length > 1 && (
              <button
                onClick={() => handleRemoveExpanded(idx)}
                className="remove-bubble-btn"
                disabled={loading}
              >
                ×
              </button>
            )}
          </div>
        ))}
        <button
          onClick={handleAddExpanded}
          className="add-bubble-btn"
          disabled={loading}
        >
          + 添加关键词
        </button>
      </div>
      
      <div className="search-controls">
        <div className="search-options">
          <label>
            最大检索数:
            <input
              type="number"
              value={maxResults}
              onChange={e => setMaxResults(parseInt(e.target.value, 10) || 1)}
              min="1"
              max="500"
              disabled={loading}
            />
          </label>
          <label>
            起始年份 (选填):
            <input
              type="number"
              placeholder="YYYY"
              value={yearLow}
              onChange={e => setYearLow(e.target.value)}
              disabled={loading}
            />
          </label>
          <label>
            结束年份 (选填):
            <input
              type="number"
              placeholder="YYYY"
              value={yearHigh}
              onChange={e => setYearHigh(e.target.value)}
              disabled={loading}
            />
          </label>
        </div>
        <button
          onClick={handleSearch}
          disabled={loading || expanded.filter(k => k.trim()).length === 0}
          className="search-button"
        >
          {loading ? '检索中...' : '开始检索论文'}
        </button>
      </div>
    </div>
  )
}

// 报告页组件
function ReportPage() {
  const navigate = useNavigate()
  const [theme, setTheme] = useState('dark')
  const toggle = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'))
  useEffect(() => {
    document.body.setAttribute('data-theme', theme)
    return () => { document.body.setAttribute('data-theme', 'dark') }
  }, [theme])
  const location = useLocation()
  const [papers] = useState(location.state?.papers || [])
  const [searchHistory] = useState(location.state?.searchHistory)
  const [expandedKeywords] = useState(location.state?.expandedKeywords || [])
  const [originalQuery] = useState(location.state?.originalQuery || '')
  const [maxResults] = useState(location.state?.maxResults || 20)
  const [expandedIdx, setExpandedIdx] = useState<{[key:number]: boolean}>({})
  const MAX_ABSTRACT = APP_CONFIG.ABSTRACT_PREVIEW_LENGTH
  const toggleAbstract = (idx: number) => setExpandedIdx(e => ({...e, [idx]: !e[idx]}))

  const handleExport = () => {
    const csvContent = [
      ['标题', '作者', '年份', '摘要', '链接'],
      ...papers.map((p: any) => [p.title, p.authors, p.year, p.abstract, p.url])
    ].map(row => row.map((cell: any) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n')
    const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = '文献报告.csv'
    link.click()
  }

  const handleBackToKeywords = () => {
    // 返回关键词页面，带上历史数据，不重新调用后端
    navigate('/keywords', { 
      state: { 
        input: originalQuery,
        expandedKeywords: expandedKeywords,
        maxResults: maxResults,
        skipExpansion: true // 标记跳过扩展
      } 
    })
  }

  return (
    <div className={`report-page ${theme === 'light' ? 'light' : 'dark'}`}> 
      <div className="report-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button 
            onClick={handleBackToKeywords}
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
            ← 返回编辑
          </button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button onClick={handleExport} className="export-button">导出CSV</button>
          <ReportThemeToggle theme={theme} toggle={toggle} />
        </div>
      </div>
      <div className="report-table-wrapper">
        <table className="report-table">
          <thead>
            <tr>
              <th className="col-title">标题</th>
              <th className="col-authors">作者</th>
              <th className="col-year">年份</th>
              <th className="col-abstract">摘要</th>
              <th className="col-link">链接</th>
            </tr>
          </thead>
          <tbody>
            {papers.map((paper: any, idx: number) => {
              const abstract = paper.abstract || ''
              const isLong = abstract.length > MAX_ABSTRACT
              const showAll = expandedIdx[idx]
              return (
                <tr key={idx}>
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
                          {showAll ? '收起' : '展开'}
                        </button>
                      )}
                    </div>
                  </td>
                  <td className="col-link">
                    <a href={paper.url} target="_blank" rel="noopener noreferrer" className="link-button">
                      查看
                    </a>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
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

// "我的"页面 - 搜索历史管理
function MyPage() {
  const navigate = useNavigate()
  const [searchHistory, setSearchHistory] = useState<SearchHistory[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [selectAll, setSelectAll] = useState(false)

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
    
    // 加载搜索历史
    loadSearchHistory()
  }, [navigate])

  const loadSearchHistory = () => {
    const history = getSearchHistory()
    setSearchHistory(history)
  }

  const handleSelectAll = () => {
    if (selectAll) {
      setSelectedIds([])
    } else {
      setSelectedIds(searchHistory.map(item => item.id))
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
    
    if (confirm(`确定要删除选中的 ${selectedIds.length} 条搜索记录吗？`)) {
      deleteSearchHistory(selectedIds)
      setSelectedIds([])
      setSelectAll(false)
      loadSearchHistory()
    }
  }

  const handleClearAll = () => {
    if (confirm('确定要清空所有搜索历史吗？此操作不可恢复。')) {
      clearAllSearchHistory()
      setSearchHistory([])
      setSelectedIds([])
      setSelectAll(false)
    }
  }

  const handleViewReport = (history: SearchHistory) => {
    // 直接查看历史报告
    navigate('/report', {
      state: {
        papers: history.papers,
        searchHistory: history,
        expandedKeywords: history.expandedKeywords,
        originalQuery: history.originalQuery,
        maxResults: history.maxResults
      }
    })
  }

  const handleReSearch = (history: SearchHistory) => {
    // 返回关键词页面重新搜索
    navigate('/keywords', {
      state: {
        input: history.originalQuery,
        expandedKeywords: history.expandedKeywords,
        maxResults: history.maxResults,
        skipExpansion: true
      }
    })
  }

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    
    if (diffDays === 0) {
      return '今天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    } else if (diffDays === 1) {
      return '昨天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    } else if (diffDays < 7) {
      return `${diffDays}天前`
    } else {
      return date.toLocaleDateString('zh-CN')
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
          borderBottom: '1px solid #333',
          paddingBottom: '16px'
        }}>
          <div>
            <h2 style={{ fontSize: 28, color: '#3bb0e6', margin: 0 }}>我的搜索历史</h2>
            <p style={{ color: '#a1a1aa', margin: '4px 0 0 0' }}>
              共 {searchHistory.length} 条记录
              {selectedIds.length > 0 && ` · 已选择 ${selectedIds.length} 条`}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <button
              onClick={() => navigate('/')}
              style={{
                padding: '8px 16px',
                borderRadius: 6,
                border: '1px solid #666',
                background: 'transparent',
                color: '#fff',
                cursor: 'pointer',
                fontSize: 14
              }}
            >
              返回首页
            </button>
          </div>
        </div>

        {/* 操作栏 */}
        {searchHistory.length > 0 && (
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
                全选
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
                删除选中 ({selectedIds.length})
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
              清空全部
            </button>
          </div>
        )}

        {/* 搜索历史列表 */}
        {searchHistory.length === 0 ? (
          <div style={{ 
            textAlign: 'center', 
            padding: '60px 20px',
            color: '#666'
          }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>📚</div>
            <h3 style={{ margin: '0 0 8px 0' }}>还没有搜索历史</h3>
            <p style={{ margin: 0 }}>开始你的第一次文献搜索吧！</p>
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
              开始搜索
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {searchHistory.map((item) => (
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
                    {/* 搜索信息 */}
                    <div style={{ marginBottom: 12 }}>
                      <h4 style={{ 
                        margin: '0 0 8px 0', 
                        fontSize: 16, 
                        color: '#fff',
                        fontWeight: 600 
                      }}>
                        "{item.originalQuery}"
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
                        <span>{item.papers.length} 篇文献</span>
                        <span>•</span>
                        <span>目标数量: {item.maxResults}</span>
                      </div>
                    </div>

                    {/* 扩展关键词 */}
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>扩展关键词:</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        {item.expandedKeywords.map((keyword, idx) => (
                          <span
                            key={idx}
                            style={{
                              padding: '2px 8px',
                              background: 'rgba(59,176,230,0.1)',
                              borderRadius: 12,
                              fontSize: 12,
                              color: '#3bb0e6',
                              border: '1px solid rgba(59,176,230,0.2)'
                            }}
                          >
                            {keyword}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* 操作按钮 */}
                    <div style={{ display: 'flex', gap: 12 }}>
                      <button
                        onClick={() => handleViewReport(item)}
                        style={{
                          padding: '6px 16px',
                          borderRadius: 6,
                          border: '1px solid #3bb0e6',
                          background: 'rgba(59,176,230,0.1)',
                          color: '#3bb0e6',
                          cursor: 'pointer',
                          fontSize: 13
                        }}
                      >
                        查看报告
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
                        重新搜索
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
      <Route path="/keywords" element={<KeywordCloudPage />} />
      <Route path="/elicit" element={<ElicitPage />} />
      <Route path="/report" element={<ReportPage />} />
      <Route path="/my" element={<MyPage />} />
      <Route path="/products" element={<ProductsPage />} />
      <Route path="/features" element={<FeaturesPage />} />
      <Route path="/admin" element={<AdminDashboard />} />
    </Routes>
  )
}

export default App
