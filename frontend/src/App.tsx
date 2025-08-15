import React, { useState, useEffect } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import './App.css'
import { registerUser } from './auth';
import ChatInterface from './ChatInterface';
import { APP_CONFIG } from './config';
import { useGlobal } from './contexts/GlobalContext';
import { ProtectedRoute } from './components/ProtectedRoute';

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

// 统一历史记录管理 - 使用localStorage
const getUnifiedHistory = async (): Promise<HistoryItem[]> => {
  const userId = localStorage.getItem('user_id');
  if (!userId) return [];

  try {
    const historyData = localStorage.getItem(`paper_god_unified_history_user_${userId}`);
    return historyData ? JSON.parse(historyData) : [];
  } catch (error) {
    console.error('获取统一历史失败:', error);
    return [];
  }
};

const deleteUnifiedHistory = async (ids: string[]) => {
  const userId = localStorage.getItem('user_id');
  if (!userId) return;

  try {
    const historyData = localStorage.getItem(`paper_god_unified_history_user_${userId}`);
    if (historyData) {
      const history: HistoryItem[] = JSON.parse(historyData);
      const filteredHistory = history.filter(item => !ids.includes(item.id));
      localStorage.setItem(`paper_god_unified_history_user_${userId}`, JSON.stringify(filteredHistory));
    }
  } catch (error) {
    console.error('删除统一历史失败:', error);
  }
};

const clearAllHistory = async () => {
  const userId = localStorage.getItem('user_id');
  if (!userId) return;

  try {
    localStorage.removeItem(`paper_god_unified_history_user_${userId}`);
  } catch (error) {
    console.error('清空所有历史失败:', error);
  }
};

// 简洁主题切换icon，仅用于报告页
// 简洁主题切换组件（移除未使用警告）

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
        {/* 已删除中英文切换按钮 */}
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
  const [isAnimating, setIsAnimating] = useState(false)
  const [typingText, setTypingText] = useState('')
  const [,] = useState(true)
  const [showUserMenu, setShowUserMenu] = useState(false)
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

  // 打字效果
  useEffect(() => {
    const fullText = "Always feel free to ask！"
    let currentIndex = 0
    let isDeleting = false
    
    const typeWriter = () => {
      if (!isDeleting && currentIndex <= fullText.length) {
        setTypingText(fullText.slice(0, currentIndex))
        currentIndex++
      } else if (isDeleting && currentIndex >= 0) {
        setTypingText(fullText.slice(0, currentIndex))
        currentIndex--
      }
      
      if (currentIndex === fullText.length + 1 && !isDeleting) {
        setTimeout(() => {
          isDeleting = true
        }, 2000) // 停留2秒
      } else if (currentIndex === -1 && isDeleting) {
        isDeleting = false
        currentIndex = 0
      }
    }
    
    const interval = setInterval(typeWriter, isDeleting ? 50 : 100)
    return () => clearInterval(interval)
  }, [])

  // 检查登录状态
  const isLoggedIn = localStorage.getItem('invite_logged_in') === '1'
  const userId = localStorage.getItem('user_id')
  const hasValidSession = isLoggedIn && userId

  // 点击外部关闭菜单
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
  }, [showUserMenu])

  // 添加全局回车键监听器
  useEffect(() => {
    const handleGlobalKeyPress = (event: KeyboardEvent) => {
      // 确保不在输入框或其他需要输入的元素中
      const target = event.target as HTMLElement
      const isInputElement = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable
      
      if (event.key === 'Enter' && !isInputElement && !event.shiftKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault()
        // 执行进入应用的逻辑
        if (!hasValidSession) {
          navigate('/invite')
        } else {
          // 触发穿梭动效
          setIsAnimating(true)
          // 延迟跳转以显示动效
          setTimeout(() => {
            // 清空当前聊天历史，开始新的聊天
            localStorage.removeItem('veritex_chat_history')
            navigate('/conversation')
          }, 400)
        }
      }
    }
    
    document.addEventListener('keydown', handleGlobalKeyPress)
    return () => document.removeEventListener('keydown', handleGlobalKeyPress)
  }, [hasValidSession, navigate])
  
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
    window.location.reload()
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!hasValidSession) {
      navigate('/invite')
      return
    }
    
    // 触发穿梭动效
    setIsAnimating(true)
    // 延迟跳转以显示动效
    setTimeout(() => {
      // 清空当前聊天历史，开始新的聊天
      localStorage.removeItem('veritex_chat_history')
      if (input.trim()) {
        navigate('/conversation', { state: { input } })
      } else {
        navigate('/conversation')
      }
    }, 400)
  }

  const handleInputClick = () => {
    if (!hasValidSession) {
      navigate('/invite')
      return
    }
    // 触发穿梭动效
    setIsAnimating(true)
    // 延迟跳转以显示动效
    setTimeout(() => {
      // 清空当前聊天历史，开始新的聊天
      localStorage.removeItem('veritex_chat_history')
      navigate('/conversation')
    }, 400)
  }

  return (
    <div className={`homepage ${isAnimating ? 'warping' : ''}`}>
      {/* 页眉 */}
      <header className="header">
        <div className="logo">Veritex</div>
        <nav className="nav">
          <ul>
            <li><a href="/products">Products</a></li>
            <li><a href="/features">Features</a></li>
            <li><a href="/pricing">Pricing</a></li>
            <li><a href="#">Support</a></li>
          </ul>
        </nav>
        <div className="header-right">
          {hasValidSession ? (
            <div className="user-menu-container" style={{ position: 'relative' }}>
              {/* 用户头像按钮 */}
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  border: 'none',
                  background: 'linear-gradient(135deg, #3bb0e6, #10b981)',
                  color: '#fff',
                  fontSize: '20px',
                  fontWeight: '900',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.3s ease',
                  boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
                  outline: 'none'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'scale(1.05)'
                  e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'scale(1)'
                  e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)'
                }}
              >
                {generateAvatar(userId || '')}
              </button>
              
              {/* 用户菜单 */}
              {showUserMenu && (
                <div style={{
                  position: 'absolute',
                  top: '50px',
                  right: '0',
                  background: '#1a1a1a',
                  border: '1px solid #333',
                  borderRadius: '8px',
                  boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)',
                  padding: '8px',
                  minWidth: '180px',
                  zIndex: 1000
                }}>
                  {/* 账号信息 */}
                  <div style={{
                    padding: '6px 10px',
                    borderBottom: '1px solid #333',
                    marginBottom: '6px'
                  }}>
                    <div style={{ fontSize: '11px', color: '#a1a1aa', marginBottom: '2px' }}>Account</div>
                    <div style={{ fontSize: '13px', color: '#fff', fontWeight: '500' }}>{userId}</div>
                  </div>
                  
                  {/* 菜单项 */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <button
                      style={{
                        padding: '6px 10px',
                        background: 'transparent',
                        border: 'none',
                        color: '#a1a1aa',
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
          ) : (
            <button className="btn btn-primary" onClick={() => navigate('/invite')}>Start free trial</button>
          )}
        </div>
      </header>
      {/* 主体内容整体左移 */}
      <main className="main" style={{ justifyContent: 'flex-start', paddingLeft: '7vw' }}>
        <section className="hero">
          <h1 className="hero-title">Smart Academic Literature Search & Management Platform</h1>
          <p className="hero-desc">
            Veritex 依托大模型与智能算法，支持关键词扩展、批量论文检索、摘要智能提取与报告导出，帮你快速定位当前的研究进展。
          </p>
          
          
          <div style={{ position: 'relative' }}>
            <form className="hero-form" onSubmit={handleSubmit}>
              <div className={`${isAnimating ? 'input-expanding' : ''}`} style={{ position: 'relative', width: '100%', maxWidth: '800px' }}>
                <input
                  type="text"
                  className="input"
                  placeholder={hasValidSession ? typingText : "请先获取内测邀请码"}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onClick={handleInputClick}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && hasValidSession) {
                      e.preventDefault()
                      handleSubmit(e as any)
                    }
                  }}
                  disabled={!hasValidSession}
                  style={{
                    cursor: hasValidSession ? 'pointer' : 'not-allowed',
                    zIndex: isAnimating ? 1001 : 1,
                    width: '100%',
                    paddingRight: hasValidSession ? '60px' : '16px'
                  }}
                />
                {/* 回车提示 - 放在输入框内部右侧 */}
                {hasValidSession && (
                  <div style={{
                    position: 'absolute',
                    right: '16px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    color: '#a1a1aa',
                    fontSize: '14px',
                    pointerEvents: 'none',
                    zIndex: isAnimating ? 1002 : 2
                  }}>
                    <span>↵</span>
                    <span style={{ fontSize: '12px' }}>Enter</span>
                  </div>
                )}
                {/* 打字光标效果 */}
                {hasValidSession && !input && (
                  <div style={{
                    position: 'absolute',
                    left: `${12 + (typingText.length * 8)}px`,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    width: '2px',
                    height: '20px',
                    background: '#3bb0e6',
                    animation: 'blink 1s infinite',
                    pointerEvents: 'none',
                    zIndex: isAnimating ? 1002 : 2
                  }} />
                )}
              </div>
              {/* 不再显示按钮，用户只需点击输入框或按回车即可 */}
            </form>
            
          </div>
          
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

      {/* 穿梭动效CSS样式 */}
      <style>
        {`
          .input-expanding {
            animation: warpTunnel 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94) forwards;
            transform-origin: center;
          }

          @keyframes warpTunnel {
            0% {
              transform: perspective(1000px) scale(1) translateZ(0) rotateX(0deg);
              opacity: 1;
              border-radius: 60px;
              box-shadow: 
                0 0 0 rgba(59, 176, 230, 0.3),
                inset 0 0 20px rgba(255, 255, 255, 0.1);
              filter: brightness(1) blur(0px);
            }
            20% {
              transform: perspective(1000px) scale(0.92) translateZ(-10px) rotateX(1deg);
              opacity: 0.95;
              border-radius: 50px;
              box-shadow: 
                0 0 20px rgba(59, 176, 230, 0.4),
                inset 0 0 25px rgba(255, 255, 255, 0.15);
              filter: brightness(1.05) blur(0px);
            }
            40% {
              transform: perspective(1000px) scale(0.75) translateZ(-30px) rotateX(2deg);
              opacity: 0.85;
              border-radius: 35px;
              box-shadow: 
                0 0 40px rgba(59, 176, 230, 0.6),
                inset 0 0 35px rgba(255, 255, 255, 0.2);
              filter: brightness(1.1) blur(0.5px);
            }
            60% {
              transform: perspective(1000px) scale(0.5) translateZ(-80px) rotateX(3deg);
              opacity: 0.7;
              border-radius: 25px;
              box-shadow: 
                0 0 70px rgba(59, 176, 230, 0.7),
                inset 0 0 45px rgba(255, 255, 255, 0.3);
              filter: brightness(1.15) blur(1px);
            }
            80% {
              transform: perspective(1000px) scale(0.25) translateZ(-150px) rotateX(4deg);
              opacity: 0.4;
              border-radius: 15px;
              box-shadow: 
                0 0 120px rgba(59, 176, 230, 0.8),
                inset 0 0 60px rgba(255, 255, 255, 0.4);
              filter: brightness(1.2) blur(1.5px);
            }
            100% {
              transform: perspective(1000px) scale(0.05) translateZ(-300px) rotateX(5deg);
              opacity: 0;
              border-radius: 50%;
              box-shadow: 
                0 0 200px rgba(59, 176, 230, 0.9),
                inset 0 0 100px rgba(255, 255, 255, 0.6);
              filter: brightness(1.3) blur(2px);
            }
          }

          /* 打字光标闪烁效果 */
          @keyframes blink {
            0%, 50% {
              opacity: 1;
            }
            51%, 100% {
              opacity: 0;
            }
          }

          /* 鼠标悬停效果 */
          .input:hover:not(:disabled) {
            box-shadow: 0 0 15px rgba(59, 176, 230, 0.3);
            transition: box-shadow 0.3s ease;
          }

          /* 确保动画不会影响页面布局 */
          .homepage {
            position: relative;
            overflow: hidden;
            perspective: 1000px;
          }

          /* 输入框样式调整 */
          .input {
            position: relative;
            transition: transform 0.8s ease, opacity 0.8s ease;
            transform-style: preserve-3d;
          }

          /* 确保动画时输入框保持在最前面 */
          .input-expanding {
            position: relative;
            z-index: 1001;
            transform-style: preserve-3d;
          }

          /* 添加穿梭背景特效 */
          .homepage::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: radial-gradient(circle at center, transparent 0%, rgba(0, 0, 0, 0.1) 100%);
            pointer-events: none;
            z-index: -1;
            transition: opacity 0.8s ease;
          }

          /* 删除背景变蓝动效，保持背景不变 */
        `}
      </style>
    </div>
  )
}


// 报告页组件
function ReportPage() {
  const navigate = useNavigate()
  const { theme, t } = useGlobal()
  const location = useLocation()
  const [papers] = useState(location.state?.papers || [])
  const [,] = useState(location.state?.expandedKeywords || [])
  const [,] = useState(location.state?.originalQuery || '')
  const [,] = useState(location.state?.maxResults || 20)
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
          {/* 导出按钮 */}
          <button onClick={handleExport} className="export-button">{t('report.export')}</button>
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
  const location = useLocation()
  const [query] = useState(location.state?.query || '')

  // 认证检查现在由ProtectedRoute处理

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
    <div className="features-page" style={{ minHeight: '100vh', background: '#000', color: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-start', paddingTop: 40 }}>
      <h1 style={{ fontSize: '3rem', fontWeight: 'bold', marginBottom: 0, marginTop: 0, letterSpacing: 1, lineHeight: 1.1, textAlign: 'center' }}>Features</h1>
      <div style={{ maxWidth: 1100, width: '100%', margin: '0 auto', marginTop: 16, textAlign: 'center' }}>
        <h2 style={{ fontWeight: 700, fontSize: '1.5rem', margin: '32px 0 12px 0', color: '#fff' }}>
          Veritex - 功能特性
        </h2>
        <p style={{ color: '#a1a1aa', fontSize: '1.15rem', margin: '0 auto', maxWidth: 900, lineHeight: 1.7 }}>
          功能特性页面正在建设中，敬请期待更多强大功能的发布！
        </p>
      </div>
    </div>
  )
}

// Pricing页面
function PricingPage() {
  return (
    <div className="pricing-page" style={{ minHeight: '100vh', background: '#000', color: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-start', paddingTop: 40 }}>
      <h1 style={{ fontSize: '3rem', fontWeight: 'bold', marginBottom: 0, marginTop: 0, letterSpacing: 1, lineHeight: 1.1, textAlign: 'center' }}>Pricing</h1>
      <div style={{ maxWidth: 1100, width: '100%', margin: '0 auto', marginTop: 16, textAlign: 'center' }}>
        <h2 style={{ fontWeight: 700, fontSize: '1.5rem', margin: '32px 0 12px 0', color: '#fff' }}>
          Veritex - 定价方案
        </h2>
        <p style={{ color: '#a1a1aa', fontSize: '1.15rem', margin: '0 auto', maxWidth: 900, lineHeight: 1.7, marginBottom: '40px' }}>
          在AI平权的时代，我们相信每个人都应该有机会接近真理，建立自己的思考体系。项目初期将全面开放，永久免费。
        </p>
        
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 40 }}>
          {/* 免费方案卡片 */}
          <div style={{ 
            background: 'linear-gradient(135deg, rgba(59, 176, 230, 0.1), rgba(16, 185, 129, 0.1))',
            border: '2px solid rgba(59, 176, 230, 0.3)',
            borderRadius: '20px',
            padding: '40px 30px',
            maxWidth: '500px',
            width: '100%',
            position: 'relative',
            boxShadow: '0 8px 32px rgba(59, 176, 230, 0.2)'
          }}>
            <div style={{ 
              position: 'absolute',
              top: '-12px',
              left: '50%',
              transform: 'translateX(-50%)',
              background: '#3bb0e6',
              color: '#fff',
              padding: '6px 20px',
              borderRadius: '20px',
              fontSize: '14px',
              fontWeight: '600'
            }}>
              推荐方案
            </div>
            
            <h3 style={{ fontSize: '2rem', fontWeight: 'bold', margin: '20px 0 10px 0', color: '#fff' }}>免费版</h3>
            <div style={{ fontSize: '3rem', fontWeight: 'bold', color: '#3bb0e6', margin: '10px 0' }}>
              ¥0 <span style={{ fontSize: '1rem', color: '#a1a1aa', fontWeight: 'normal' }}>/永久</span>
            </div>
            
            <ul style={{ 
              listStyle: 'none', 
              padding: 0, 
              margin: '30px 0', 
              textAlign: 'left',
              color: '#fff',
              fontSize: '1.1rem',
              lineHeight: '2'
            }}>
              <li style={{ marginBottom: '12px' }}>✅ 无限制关键词扩展</li>
              <li style={{ marginBottom: '12px' }}>✅ 批量论文检索</li>
              <li style={{ marginBottom: '12px' }}>✅ 智能摘要提取</li>
              <li style={{ marginBottom: '12px' }}>✅ 报告导出功能</li>
              <li style={{ marginBottom: '12px' }}>✅ 多学科支持</li>
              <li style={{ marginBottom: '12px' }}>✅ 云端数据同步</li>
            </ul>
            
            <button style={{
              width: '100%',
              padding: '16px',
              background: '#3bb0e6',
              color: '#fff',
              border: 'none',
              borderRadius: '12px',
              fontSize: '18px',
              fontWeight: '600',
              cursor: 'pointer',
              transition: 'all 0.3s ease'
            }}
            onMouseEnter={(e) => (e.target as HTMLButtonElement).style.background = '#2da5d9'}
            onMouseLeave={(e) => (e.target as HTMLButtonElement).style.background = '#3bb0e6'}>
              立即开始使用
            </button>
          </div>
          
          {/* 未来计划 */}
          <div style={{ textAlign: 'center', marginTop: '20px' }}>
            <p style={{ color: '#a1a1aa', fontSize: '1rem', lineHeight: 1.8 }}>
              我们承诺在项目发展过程中始终保持核心功能免费。<br/>
              未来可能推出的高级功能将以可选付费形式提供，但基础研究功能永远免费。
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// "我的"页面 - 历史记录管理  
function MyPage() {
  const navigate = useNavigate()
  const [unifiedHistory, setUnifiedHistory] = useState<HistoryItem[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [selectAll, setSelectAll] = useState(false)
  const [filter, setFilter] = useState<'search' | 'chat'>('search')
  // useGlobal hook available but not currently needed

  // 认证检查现在由ProtectedRoute处理
  useEffect(() => {
    // 加载历史记录
    loadHistory()
  }, [])

  const loadHistory = async () => {
    const history = await getUnifiedHistory()
    setUnifiedHistory(history)
  }

  const filteredHistory = unifiedHistory.filter(item => item.type === filter)

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

  const handleDeleteSelected = async () => {
    if (selectedIds.length === 0) return
    
    if (confirm(`确定要删除选中的 ${selectedIds.length} 条记录吗？`)) {
      await deleteUnifiedHistory(selectedIds)
      setSelectedIds([])
      setSelectAll(false)
      await loadHistory()
    }
  }

  const handleClearAll = async () => {
    if (confirm('确定要清空所有历史记录吗？此操作不可恢复。')) {
      await clearAllHistory()
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
          <div style={{ display: 'flex', alignItems: 'center' }}>
            {/* 左侧过滤器按钮组 - 框选样式 */}
            <div style={{ 
              display: 'flex',
              background: '#111',
              borderRadius: 8,
              border: '1px solid #333',
              padding: '4px'
            }}>
              {([
                { key: 'search', label: 'Search Result' }, 
                { key: 'chat', label: 'Chat' }
              ] as const).map(filterType => (
                <button
                  key={filterType.key}
                  onClick={() => setFilter(filterType.key as 'search' | 'chat')}
                  style={{
                    padding: '6px 16px',
                    borderRadius: 4,
                    border: 'none',
                    background: filter === filterType.key ? 'var(--accent-primary)' : 'transparent',
                    color: filter === filterType.key ? '#fff' : 'var(--text-secondary)',
                    cursor: 'pointer',
                    fontSize: 14,
                    transition: 'all 0.2s ease'
                  }}
                >
                  {filterType.label}
                </button>
              ))}
            </div>
            {/* 右侧Home按钮 - 与左侧保持距离 */}
            <button
              onClick={() => navigate('/')}
              style={{
                padding: '6px 16px',
                borderRadius: 6,
                border: '1px solid var(--border-primary)',
                background: 'transparent',
                color: 'var(--text-primary)',
                cursor: 'pointer',
                fontSize: 14,
                marginLeft: '32px'  // 与左侧双按钮组保持距离
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
      <Route path="/products" element={<ProductsPage />} />
      <Route path="/features" element={<FeaturesPage />} />
      <Route path="/pricing" element={<PricingPage />} />
      
      {/* 需要认证的路由 */}
      <Route path="/conversation" element={
        <ProtectedRoute>
          <ChatInterface />
        </ProtectedRoute>
      } />
      <Route path="/elicit" element={
        <ProtectedRoute>
          <ElicitPage />
        </ProtectedRoute>
      } />
      <Route path="/report" element={
        <ProtectedRoute>
          <ReportPage />
        </ProtectedRoute>
      } />
      <Route path="/my" element={
        <ProtectedRoute>
          <MyPage />
        </ProtectedRoute>
      } />
    </Routes>
  )
}

export default App
