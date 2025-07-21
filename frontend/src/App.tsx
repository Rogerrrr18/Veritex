import React, { useState, useEffect, createContext, useContext } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import './App.css'
import { supabase, registerUser, logUserAction } from './supabaseClient';
import AdminDashboard from './AdminDashboard';

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
              {hasValidSession ? 'Find your paper' : '获取内测邀请码'}
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
  const [expanded, setExpanded] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [maxResults, setMaxResults] = useState<number>(20)
  const [yearLow, setYearLow] = useState<string>('')
  const [yearHigh, setYearHigh] = useState<string>('')
  const [showLoading, setShowLoading] = useState(false)

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
    if (input) {
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
      // 如果没有用户ID，清除登录状态并跳转
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
      
      const res = await fetch('/expand_keywords', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          keywords: input,
          user_id: userId 
        })
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: '扩展失败，无法解析错误响应' }))
        // 如果是401错误，说明用户未登录或无效
        if (res.status === 401) {
          localStorage.removeItem('invite_logged_in')
          localStorage.removeItem('user_id')
          navigate('/invite')
          return
        }
        throw new Error(errData.detail || `HTTP error ${res.status}`)
      }
      const data = await res.json()
      setExpanded(data.expanded_terms || [])
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
      
      const payload = {
        keywords: validKeywords,
        max_results: maxResults,
        year_low: yearLow ? parseInt(yearLow, 10) : null,
        year_high: yearHigh ? parseInt(yearHigh, 10) : null,
        user_id: userId
      }
      
      const res = await fetch('/search_papers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: '爬取失败，无法解析错误响应' }))
        // 如果是401错误，说明用户未登录或无效
        if (res.status === 401) {
          localStorage.removeItem('invite_logged_in')
          localStorage.removeItem('user_id')
          navigate('/invite')
          return
        }
        throw new Error(errData.detail || `HTTP error ${res.status}`)
      }
      
      const data = await res.json()
      navigate('/report', { state: { papers: data.papers || [] } })
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
  const [theme, setTheme] = useState('dark')
  const toggle = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'))
  useEffect(() => {
    document.body.setAttribute('data-theme', theme)
    return () => { document.body.setAttribute('data-theme', 'dark') }
  }, [theme])
  const location = useLocation()
  const [papers] = useState(location.state?.papers || [])
  const [expandedIdx, setExpandedIdx] = useState<{[key:number]: boolean}>({})
  const MAX_ABSTRACT = 120
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

  return (
    <div className={`report-page ${theme === 'light' ? 'light' : 'dark'}`}> 
      <div className="report-header">
        <h2>文献报告</h2>
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

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/invite" element={<InviteCodePage />} />
      <Route path="/keywords" element={<KeywordCloudPage />} />
      <Route path="/report" element={<ReportPage />} />
      <Route path="/products" element={<ProductsPage />} />
      <Route path="/features" element={<FeaturesPage />} />
      <Route path="/admin" element={<AdminDashboard />} />
    </Routes>
  )
}

export default App
