import { useState } from 'react'
import { Routes, Route, useNavigate } from 'react-router-dom'
import './App.css'

// Interface for paper data (if we were to display it directly)
// interface Paper {
//   title: string;
//   authors: string;
//   year: string;
//   abstract: string;
//   url: string;
// }

// 新增：报告页组件
function ReportPage({ papers }: { papers: any[] }) {
  // 展开状态数组
  const [expandedIdx, setExpandedIdx] = useState<{[key:number]: boolean}>({});
  const MAX_ABSTRACT = 120;
  const toggle = (idx: number) => setExpandedIdx(e => ({...e, [idx]: !e[idx]}));
  return (
    <div className="report-container">
      <h2>文献报告</h2>
      <div className="report-table-wrapper">
        <table className="report-table">
          <thead>
            <tr>
              <th>标题</th>
              <th>作者</th>
              <th>年份</th>
              <th>摘要</th>
              <th>链接</th>
            </tr>
          </thead>
          <tbody>
            {papers.map((paper, idx) => {
              const abstract = paper.abstract || '';
              const isLong = abstract.length > MAX_ABSTRACT;
              const showAll = expandedIdx[idx];
              return (
                <tr key={idx}>
                  <td>{paper.title}</td>
                  <td>{paper.authors}</td>
                  <td>{paper.year}</td>
                  <td style={{maxWidth: 600, wordBreak: 'break-all'}}>
                    {isLong && !showAll
                      ? abstract.slice(0, MAX_ABSTRACT) + '...'
                      : abstract}
                    {isLong && (
                      <button className="abstract-toggle" onClick={() => toggle(idx)}>
                        {showAll ? '收起' : '展开'}
                      </button>
                    )}
                  </td>
                  <td><a href={paper.url} target="_blank" rel="noopener noreferrer">查看</a></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function App() {
  const [input, setInput] = useState('')
  const [expanded, setExpanded] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState<'input'|'expanding'|'expanded'|'searching'|'done'>('input')
  const [error, setError] = useState('')
  const [maxResults, setMaxResults] = useState<number>(20)
  const [yearLow, setYearLow] = useState<string>('') // Use string for input, parse to number later
  const [yearHigh, setYearHigh] = useState<string>('')
  const [papers, setPapers] = useState<any[]>([])
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null) // For the XLSX download link
  const [lastSearchMessage, setLastSearchMessage] = useState<string>('')
  const navigate = useNavigate()

  // Reset relevant state when input changes
  const handleInputChange = (value: string) => {
    setInput(value)
    setStep('input')
    setExpanded([])
    setError('')
    setDownloadUrl(null)
    setLastSearchMessage('')
  }

  // 关键词扩展
  const handleExpand = async () => {
    setError('')
    setDownloadUrl(null)
    setLastSearchMessage('')
    if (!input.trim()) {
      setError('请输入关键词')
      return
    }
    setStep('expanding')
    setLoading(true)
    try {
      const res = await fetch('/expand_keywords', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keywords: input })
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: '扩展失败，无法解析错误响应' }))
        throw new Error(errData.detail || `HTTP error ${res.status}`)
      }
      const data = await res.json()
      setExpanded(data.expanded_terms || [])
      setStep('expanded')
    } catch (e: any) {
      setError(e.message || '扩展关键词失败')
      setStep('input') // Revert to input step on error
    }
    setLoading(false)
  }

  // 论文爬取
  const handleSearch = async () => {
    setError('')
    setDownloadUrl(null)
    setLastSearchMessage('')
    if (expanded.length === 0) {
      setError('请先扩展关键词或确保有可用关键词')
      return
    }
    setStep('searching')
    setLoading(true)
    try {
      const payload = {
        keywords: expanded,
        max_results: maxResults,
        year_low: yearLow ? parseInt(yearLow, 10) : null,
        year_high: yearHigh ? parseInt(yearHigh, 10) : null,
      }
      if (payload.year_low && isNaN(payload.year_low)) throw new Error('起始年份格式无效')
      if (payload.year_high && isNaN(payload.year_high)) throw new Error('结束年份格式无效')

      const res = await fetch('/search_papers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: '爬取失败，无法解析错误响应' }))
        throw new Error(errData.detail || `HTTP error ${res.status}`)
      }
      const data = await res.json()
      setLastSearchMessage(data.message || '爬取完成，数据已处理。')
      setPapers(data.papers || [])
      setStep('done')
    } catch (e: any) {
      setError(e.message || '爬取论文失败')
      setStep('expanded') // Revert to expanded step on error
    }
    setLoading(false)
  }

  return (
    <Routes>
      <Route path="/" element={
        <div className="container">
          <h2>智能论文检索系统</h2>
          
          <div className="card input-card">
            <input
              type="text"
              placeholder="请输入英文关键词"
              value={input}
              onChange={e => handleInputChange(e.target.value)}
              disabled={loading && step !== 'input'}
            />
            <button onClick={handleExpand} disabled={loading || step!=='input'}>
              {step === 'expanding' ? '扩展中...' : '关键词扩展'}
            </button>
          </div>

          {error && <p className="error-message">错误: {error}</p>}

          {expanded.length > 0 && step !== 'input' && step !== 'expanding' && (
            <div className="card expanded-card">
              <p><b>扩展结果：</b> <span className="expanded-terms">{expanded.join(', ')}</span></p>
              
              <div className="search-options">
                <label>
                  最大检索数:
                  <input 
                    type="number" 
                    value={maxResults} 
                    onChange={e => setMaxResults(parseInt(e.target.value, 10) || 1)} 
                    min="1" 
                    max="500" // Reasonable max for web UI
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
              <button onClick={handleSearch} disabled={loading || step!=='expanded'} className="search-button">
                {step === 'searching' ? '检索中...' : '开始检索论文'}
              </button>
            </div>
          )}

          {step === 'searching' && <p className="status-message">正在检索论文并生成报告...</p>}
          
          {step === 'done' && (
            <div className="card results-card">
                <p className="status-message success-message">{lastSearchMessage}</p>
                <button className="view-report-button" onClick={() => navigate('/report', { state: { papers } })}>
                    查看报告
                </button>
            </div>
          )}
        </div>
      } />
      <Route path="/report" element={<ReportPage papers={(window.history.state && window.history.state.usr && window.history.state.usr.papers) || []} />} />
    </Routes>
  )
}

export default App
