import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../config';

interface HierarchicalKeywords {
  exact_terms?: {
    terms: string[];
    weight: number;
  };
  core_synonyms?: {
    terms: string[];
    weight: number;
  };
  related_terms?: {
    terms: string[];
    weight: number;
  };
  context_terms?: {
    terms: string[];
    weight: number;
  };
}

interface KeywordCloudWidgetProps {
  hierarchicalKeywords: HierarchicalKeywords | null;
  originalQuery?: string;
  isDraggable?: boolean;
}

interface SearchSettings {
  maxResults: number;
  yearFrom: string;
  yearTo: string;
}

interface KeywordItem {
  term: string;
  level: string;
  weight: number;
  color: string;
  editable?: boolean;
}

const KeywordCloudWidget: React.FC<KeywordCloudWidgetProps> = ({
  hierarchicalKeywords,
  originalQuery = '',
  isDraggable = true
}) => {
  const navigate = useNavigate();
  const [keywords, setKeywords] = useState<KeywordItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [newKeyword, setNewKeyword] = useState('');
  const [searchSettings, setSearchSettings] = useState<SearchSettings>({
    maxResults: 20,
    yearFrom: '',
    yearTo: ''
  });
  const [showSettings, setShowSettings] = useState(false);
  const [draggedKeyword, setDraggedKeyword] = useState<KeywordItem | null>(null);

  // 颜色配置：不同层级使用不同颜色
  const levelColors = {
    exact_terms: '#3b82f6',      // 蓝色 - 精确术语
    core_synonyms: '#10b981',    // 绿色 - 核心同义词
    related_terms: '#f59e0b',    // 橙色 - 相关术语  
    context_terms: '#8b5cf6'     // 紫色 - 上下文术语
  };

  // 层级中文名称
  const levelNames = {
    exact_terms: '精确术语',
    core_synonyms: '核心同义词',
    related_terms: '相关术语',
    context_terms: '上下文术语'
  };

  // 解析层次化关键词数据
  useEffect(() => {
    if (!hierarchicalKeywords) {
      setKeywords([]);
      return;
    }

    const newKeywords: KeywordItem[] = [];

    // 按层级处理关键词
    Object.entries(hierarchicalKeywords).forEach(([level, data]) => {
      if (data && data.terms && Array.isArray(data.terms)) {
        data.terms.forEach((term: string) => {
          if (term && term.trim()) {
            newKeywords.push({
              term: term.trim(),
              level,
              weight: data.weight || 1.0,
              color: levelColors[level as keyof typeof levelColors] || '#6b7280'
            });
          }
        });
      }
    });

    setKeywords(newKeywords);
  }, [hierarchicalKeywords]);

  // 添加新关键词
  const handleAddKeyword = () => {
    if (!newKeyword.trim()) return;
    
    const newItem: KeywordItem = {
      term: newKeyword.trim(),
      level: 'context_terms',
      weight: 0.5,
      color: levelColors.context_terms,
      editable: true
    };
    
    setKeywords(prev => [...prev, newItem]);
    setNewKeyword('');
  };

  // 删除关键词
  const handleRemoveKeyword = (index: number) => {
    setKeywords(prev => prev.filter((_, i) => i !== index));
  };

  // 拖拽功能
  const handleDragStart = (e: React.DragEvent, keyword: KeywordItem) => {
    if (!isDraggable) return;
    setDraggedKeyword(keyword);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent) => {
    if (!isDraggable) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e: React.DragEvent, targetLevel: string) => {
    if (!isDraggable || !draggedKeyword) return;
    e.preventDefault();
    
    // 只允许在不同层级之间拖拽
    if (draggedKeyword.level !== targetLevel) {
      setKeywords(prev => prev.map(keyword => 
        keyword === draggedKeyword 
          ? { ...keyword, level: targetLevel, color: levelColors[targetLevel as keyof typeof levelColors] }
          : keyword
      ));
    }
    
    setDraggedKeyword(null);
  };

  const handleDragEnd = () => {
    setDraggedKeyword(null);
  };

  // 编辑关键词
  const handleEditKeyword = (index: number, newTerm: string) => {
    if (!newTerm.trim()) {
      handleRemoveKeyword(index);
      return;
    }
    
    setKeywords(prev => prev.map((item, i) => 
      i === index ? { ...item, term: newTerm.trim() } : item
    ));
  };

  // 执行搜索并跳转到报告页面
  const handleSearchPapers = async () => {
    if (keywords.length === 0) {
      alert('请先添加一些关键词');
      return;
    }

    setIsLoading(true);

    try {
      // 构建搜索查询：按层级权重组合关键词
      const exactTerms = keywords.filter(k => k.level === 'exact_terms').map(k => k.term);
      const coreTerms = keywords.filter(k => k.level === 'core_synonyms').map(k => k.term);
      const relatedTerms = keywords.filter(k => k.level === 'related_terms').map(k => k.term);
      const contextTerms = keywords.filter(k => k.level === 'context_terms').map(k => k.term);

      // 构建布尔查询：精确术语 AND (核心同义词 OR 相关术语) AND 上下文术语
      let queryParts = [];
      
      if (exactTerms.length > 0) {
        queryParts.push(`(${exactTerms.map(t => `"${t}"`).join(' AND ')})`);
      }
      
      if (coreTerms.length > 0 || relatedTerms.length > 0) {
        const synonymParts = [...coreTerms, ...relatedTerms];
        queryParts.push(`(${synonymParts.join(' OR ')})`);
      }
      
      if (contextTerms.length > 0) {
        queryParts.push(`(${contextTerms.join(' OR ')})`);
      }

      const searchQuery = queryParts.join(' AND ') || keywords.map(k => k.term).join(' OR ');

      // 调用搜索API，使用用户设置的参数
      const searchResult = await api.searchPapers(searchQuery, searchSettings.maxResults, false);
      
      // 处理搜索结果
      const papers = searchResult.success && searchResult.data 
        ? searchResult.data.papers 
        : (searchResult.papers || []);

      // 创建搜索历史记录
      const searchHistory = {
        id: Date.now().toString(),
        timestamp: Date.now(),
        originalQuery: originalQuery || '关键词云搜索',
        expandedKeywords: keywords.map(k => k.term),
        papers: papers,
        maxResults: searchSettings.maxResults
      };

      // 跳转到报告页面
      navigate('/report', {
        state: {
          papers,
          searchHistory,
          expandedKeywords: keywords.map(k => k.term),
          originalQuery: originalQuery || '关键词云搜索',
          maxResults: searchSettings.maxResults,
          searchSource: 'keyword_cloud' // 标记来源
        }
      });

    } catch (error: any) {
      console.error('Search failed:', error);
      alert(`搜索失败：${error.message || '未知错误'}`);
    } finally {
      setIsLoading(false);
    }
  };

  // 如果没有关键词数据，显示空状态
  if (!hierarchicalKeywords && keywords.length === 0) {
    return (
      <div style={{
        padding: '20px',
        textAlign: 'center',
        color: '#6b7280',
        fontSize: '14px'
      }}>
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>🔍</div>
        <div>发送学术查询后</div>
        <div>关键词云将在这里显示</div>
      </div>
    );
  }

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      padding: '16px',
      backgroundColor: '#f8f9fa',
      borderLeft: '1px solid #e9ecef'
    }}>
      {/* 标题栏 */}
      <div style={{
        marginBottom: '16px',
        paddingBottom: '12px',
        borderBottom: '2px solid #e9ecef'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h4 style={{ 
              margin: '0 0 4px 0', 
              fontSize: '16px', 
              color: '#333',
              fontWeight: '600'
            }}>
              🏷️ 关键词云
            </h4>
            <div style={{ fontSize: '12px', color: '#6b7280' }}>
              {keywords.length} 个关键词 • {isDraggable ? '拖拽编辑' : '点击编辑'}
            </div>
          </div>
          <button
            onClick={() => setShowSettings(!showSettings)}
            style={{
              padding: '4px 8px',
              fontSize: '12px',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              background: '#fff',
              cursor: 'pointer',
              color: '#374151'
            }}
          >
            ⚙️ 设置
          </button>
        </div>
        
        {/* 搜索设置面板 */}
        {showSettings && (
          <div style={{
            marginTop: '12px',
            padding: '12px',
            backgroundColor: '#f9fafb',
            borderRadius: '6px',
            border: '1px solid #e5e7eb'
          }}>
            <div style={{ fontSize: '12px', fontWeight: '600', marginBottom: '8px', color: '#374151' }}>
              搜索参数设置
            </div>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <div>
                <label style={{ fontSize: '11px', color: '#6b7280', display: 'block', marginBottom: '2px' }}>
                  论文数目
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={searchSettings.maxResults}
                  onChange={(e) => setSearchSettings(prev => ({
                    ...prev,
                    maxResults: Math.min(100, Math.max(1, parseInt(e.target.value) || 20))
                  }))}
                  style={{
                    width: '60px',
                    padding: '4px 6px',
                    fontSize: '11px',
                    border: '1px solid #d1d5db',
                    borderRadius: '3px'
                  }}
                />
              </div>
              <div>
                <label style={{ fontSize: '11px', color: '#6b7280', display: 'block', marginBottom: '2px' }}>
                  起始年份
                </label>
                <input
                  type="number"
                  min="1900"
                  max={new Date().getFullYear()}
                  value={searchSettings.yearFrom}
                  onChange={(e) => setSearchSettings(prev => ({ ...prev, yearFrom: e.target.value }))}
                  placeholder="2020"
                  style={{
                    width: '60px',
                    padding: '4px 6px',
                    fontSize: '11px',
                    border: '1px solid #d1d5db',
                    borderRadius: '3px'
                  }}
                />
              </div>
              <div>
                <label style={{ fontSize: '11px', color: '#6b7280', display: 'block', marginBottom: '2px' }}>
                  结束年份
                </label>
                <input
                  type="number"
                  min="1900"
                  max={new Date().getFullYear()}
                  value={searchSettings.yearTo}
                  onChange={(e) => setSearchSettings(prev => ({ ...prev, yearTo: e.target.value }))}
                  placeholder="2024"
                  style={{
                    width: '60px',
                    padding: '4px 6px',
                    fontSize: '11px',
                    border: '1px solid #d1d5db',
                    borderRadius: '3px'
                  }}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 关键词云区域 */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        marginBottom: '16px'
      }}>
        {/* 按层级分组显示 */}
        {Object.entries(levelNames).map(([level, name]) => {
          const levelKeywords = keywords.filter(k => k.level === level);
          if (levelKeywords.length === 0) return null;

          return (
            <div 
              key={level} 
              style={{ marginBottom: '16px' }}
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(e, level)}
            >
              <div style={{
                fontSize: '12px',
                color: levelColors[level as keyof typeof levelColors],
                fontWeight: '600',
                marginBottom: '8px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}>
                <div
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: levelColors[level as keyof typeof levelColors]
                  }}
                />
                {name} ({levelKeywords.length})
                {isDraggable && <span style={{ fontSize: '10px', color: '#9ca3af' }}>拖放区域</span>}
              </div>
              
              <div style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: '6px',
                marginBottom: '8px'
              }}>
                {levelKeywords.map((keyword, index) => (
                  <div
                    key={`${keyword.level}-${index}`}
                    draggable={isDraggable}
                    onDragStart={(e) => handleDragStart(e, keyword)}
                    onDragEnd={handleDragEnd}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '4px 8px',
                      backgroundColor: keyword.color,
                      color: 'white',
                      borderRadius: '12px',
                      fontSize: '12px',
                      fontWeight: '500',
                      cursor: isDraggable ? 'move' : 'pointer',
                      transition: 'all 0.2s',
                      opacity: draggedKeyword === keyword ? 0.5 : 0.9
                    }}
                    onMouseEnter={(e) => {
                      if (draggedKeyword !== keyword) {
                        e.currentTarget.style.opacity = '1';
                        e.currentTarget.style.transform = 'scale(1.05)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (draggedKeyword !== keyword) {
                        e.currentTarget.style.opacity = '0.9';
                        e.currentTarget.style.transform = 'scale(1)';
                      }
                    }}
                  >
                    <input
                      type="text"
                      value={keyword.term}
                      onChange={(e) => handleEditKeyword(keywords.indexOf(keyword), e.target.value)}
                      onBlur={(e) => {
                        if (!e.target.value.trim()) {
                          handleRemoveKeyword(keywords.indexOf(keyword));
                        }
                      }}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'white',
                        fontSize: '12px',
                        outline: 'none',
                        width: `${Math.max(keyword.term.length * 8, 40)}px`,
                        minWidth: '40px'
                      }}
                    />
                    <button
                      onClick={() => handleRemoveKeyword(keywords.indexOf(keyword))}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'white',
                        cursor: 'pointer',
                        fontSize: '14px',
                        padding: '0',
                        lineHeight: 1,
                        opacity: 0.7
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
                      onMouseLeave={(e) => e.currentTarget.style.opacity = '0.7'}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        {/* 添加新关键词 */}
        <div style={{
          marginTop: '16px',
          padding: '12px',
          backgroundColor: '#fff',
          borderRadius: '8px',
          border: '1px dashed #d1d5db'
        }}>
          <div style={{
            display: 'flex',
            gap: '8px',
            alignItems: 'center'
          }}>
            <input
              type="text"
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  handleAddKeyword();
                }
              }}
              placeholder="添加新关键词..."
              style={{
                flex: 1,
                padding: '6px 10px',
                fontSize: '12px',
                border: '1px solid #d1d5db',
                borderRadius: '4px',
                outline: 'none'
              }}
            />
            <button
              onClick={handleAddKeyword}
              disabled={!newKeyword.trim()}
              style={{
                padding: '6px 10px',
                fontSize: '12px',
                backgroundColor: newKeyword.trim() ? '#3b82f6' : '#9ca3af',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: newKeyword.trim() ? 'pointer' : 'not-allowed'
              }}
            >
              添加
            </button>
          </div>
        </div>
      </div>

      {/* 搜索按钮 */}
      <div style={{
        marginTop: 'auto',
        paddingTop: '16px',
        borderTop: '1px solid #e9ecef'
      }}>
        <button
          onClick={handleSearchPapers}
          disabled={isLoading || keywords.length === 0}
          style={{
            width: '100%',
            padding: '12px',
            backgroundColor: keywords.length > 0 && !isLoading ? '#10b981' : '#9ca3af',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            fontSize: '14px',
            fontWeight: '600',
            cursor: keywords.length > 0 && !isLoading ? 'pointer' : 'not-allowed',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => {
            if (keywords.length > 0 && !isLoading) {
              e.currentTarget.style.backgroundColor = '#059669';
              e.currentTarget.style.transform = 'translateY(-1px)';
            }
          }}
          onMouseLeave={(e) => {
            if (keywords.length > 0 && !isLoading) {
              e.currentTarget.style.backgroundColor = '#10b981';
              e.currentTarget.style.transform = 'translateY(0)';
            }
          }}
        >
          {isLoading ? (
            <>
              <div style={{
                width: '14px',
                height: '14px',
                border: '2px solid rgba(255,255,255,0.3)',
                borderTop: '2px solid white',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite'
              }} />
              搜索中...
            </>
          ) : (
            <>
              🔍 搜索论文 ({keywords.length})
            </>
          )}
        </button>
        
        {/* 提示文本 */}
        <div style={{
          marginTop: '8px',
          fontSize: '11px',
          color: '#6b7280',
          textAlign: 'center'
        }}>
          点击搜索后将跳转到报告页面
        </div>
      </div>

      {/* 添加旋转动画 */}
      <style>
        {`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}
      </style>
    </div>
  );
};

export default KeywordCloudWidget;