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

  // 颜色配置：不同层级使用不同颜色
  const levelColors = {
    exact_terms: '#3b82f6',      // 蓝色 - 精确术语
    core_synonyms: '#10b981',    // 绿色 - 核心同义词
    related_terms: '#f59e0b',    // 橙色 - 相关术语  
    context_terms: '#8b5cf6'     // 紫色 - 上下文术语
  };

  // 层级名称
  const levelNames = {
    exact_terms: 'Exact Terms',
    core_synonyms: 'Core Synonyms',
    related_terms: 'Related Terms',
    context_terms: 'Context Terms'
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

  // 添加自定义关键词
  const addCustomKeyword = () => {
    if (newKeyword.trim()) {
      setKeywords(prev => [...prev, {
        term: newKeyword.trim(),
        level: 'custom',
        weight: 1.0,
        color: '#6366f1',
        editable: true
      }]);
      setNewKeyword('');
    }
  };

  // 删除关键词
  const removeKeyword = (index: number) => {
    setKeywords(prev => prev.filter((_, i) => i !== index));
  };

  // 执行搜索
  const handleSearch = async () => {
    if (keywords.length === 0) {
      alert('请先添加关键词');
      return;
    }

    setIsLoading(true);

    try {
      // 构建搜索查询
      const searchQuery = keywords.map(k => k.term).join(' OR ');

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
        originalQuery: originalQuery || 'Keywords Search',
        expandedKeywords: keywords.map(k => k.term),
        papers: papers,
        maxResults: searchSettings.maxResults
      };

      // 保存搜索历史
      const STORAGE_KEY = 'paper_god_search_history';
      const existingHistory = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
      existingHistory.unshift(searchHistory);
      if (existingHistory.length > 50) {
        existingHistory.splice(50);
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(existingHistory));

      // 跳转到报告页面
      navigate('/report', {
        state: {
          papers,
          searchHistory,
          expandedKeywords: keywords.map(k => k.term),
          originalQuery: originalQuery || 'Keywords Search',
          maxResults: searchSettings.maxResults,
          searchSource: 'keyword_cloud'
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
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#0a0a0a'
      }}>
        {/* 搜索参数设置区域 */}
        <div style={{
          padding: '16px',
          backgroundColor: '#111',
          borderBottom: '1px solid #333'
        }}>
          <h4 style={{ 
            margin: '0 0 12px 0', 
            fontSize: '14px', 
            color: '#fff',
            fontWeight: '600'
          }}>
            Search Parameters
          </h4>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {/* 论文数量 */}
            <div>
              <label style={{ 
                display: 'block', 
                fontSize: '12px', 
                color: '#a1a1aa', 
                marginBottom: '6px' 
              }}>
                Max Papers
              </label>
              <input
                type="number"
                value={searchSettings.maxResults}
                onChange={(e) => setSearchSettings(prev => ({
                  ...prev,
                  maxResults: parseInt(e.target.value) || 20
                }))}
                min="1"
                max="100"
                style={{
                  width: '100%',
                  padding: '8px',
                  fontSize: '13px',
                  border: '1px solid #333',
                  borderRadius: '6px',
                  backgroundColor: '#1a1a1a',
                  color: '#fff',
                  outline: 'none'
                }}
              />
            </div>
            
            {/* 时间范围 */}
            <div style={{ display: 'flex', gap: '8px' }}>
              <div style={{ flex: 1 }}>
                <label style={{ 
                  display: 'block', 
                  fontSize: '12px', 
                  color: '#a1a1aa', 
                  marginBottom: '6px' 
                }}>
                  From Year
                </label>
                <input
                  type="number"
                  placeholder="2020"
                  value={searchSettings.yearFrom}
                  onChange={(e) => setSearchSettings(prev => ({
                    ...prev,
                    yearFrom: e.target.value
                  }))}
                  style={{
                    width: '100%',
                    padding: '8px',
                    fontSize: '13px',
                    border: '1px solid #333',
                    borderRadius: '6px',
                    backgroundColor: '#1a1a1a',
                    color: '#fff',
                    outline: 'none'
                  }}
                />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ 
                  display: 'block', 
                  fontSize: '12px', 
                  color: '#a1a1aa', 
                  marginBottom: '6px' 
                }}>
                  To Year
                </label>
                <input
                  type="number"
                  placeholder="2024"
                  value={searchSettings.yearTo}
                  onChange={(e) => setSearchSettings(prev => ({
                    ...prev,
                    yearTo: e.target.value
                  }))}
                  style={{
                    width: '100%',
                    padding: '8px',
                    fontSize: '13px',
                    border: '1px solid #333',
                    borderRadius: '6px',
                    backgroundColor: '#1a1a1a',
                    color: '#fff',
                    outline: 'none'
                  }}
                />
              </div>
            </div>
          </div>
        </div>

        <div style={{
          flex: 1,
          padding: '20px',
          textAlign: 'center',
          color: '#6b7280',
          fontSize: '14px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>⌕</div>
          <div>Send academic queries</div>
          <div>Keywords cloud will appear here</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: '#0a0a0a'
    }}>
      {/* 搜索参数设置区域 - 移至顶部 */}
      <div style={{
        padding: '16px',
        backgroundColor: '#111',
        borderBottom: '1px solid #333'
      }}>
        <h4 style={{ 
          margin: '0 0 12px 0', 
          fontSize: '14px', 
          color: '#fff',
          fontWeight: '600'
        }}>
          Search Parameters
        </h4>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* 论文数量 */}
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: '12px', 
              color: '#a1a1aa', 
              marginBottom: '6px' 
            }}>
              Max Papers
            </label>
            <input
              type="number"
              value={searchSettings.maxResults}
              onChange={(e) => setSearchSettings(prev => ({
                ...prev,
                maxResults: parseInt(e.target.value) || 20
              }))}
              min="1"
              max="100"
              style={{
                width: '100%',
                padding: '8px',
                fontSize: '13px',
                border: '1px solid #333',
                borderRadius: '6px',
                backgroundColor: '#1a1a1a',
                color: '#fff',
                outline: 'none'
              }}
            />
          </div>
          
          {/* 时间范围 */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <div style={{ flex: 1 }}>
              <label style={{ 
                display: 'block', 
                fontSize: '12px', 
                color: '#a1a1aa', 
                marginBottom: '6px' 
              }}>
                From Year
              </label>
              <input
                type="number"
                placeholder="2020"
                value={searchSettings.yearFrom}
                onChange={(e) => setSearchSettings(prev => ({
                  ...prev,
                  yearFrom: e.target.value
                }))}
                style={{
                  width: '100%',
                  padding: '8px',
                  fontSize: '13px',
                  border: '1px solid #333',
                  borderRadius: '6px',
                  backgroundColor: '#1a1a1a',
                  color: '#fff',
                  outline: 'none'
                }}
              />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ 
                display: 'block', 
                fontSize: '12px', 
                color: '#a1a1aa', 
                marginBottom: '6px' 
              }}>
                To Year
              </label>
              <input
                type="number"
                placeholder="2024"
                value={searchSettings.yearTo}
                onChange={(e) => setSearchSettings(prev => ({
                  ...prev,
                  yearTo: e.target.value
                }))}
                style={{
                  width: '100%',
                  padding: '8px',
                  fontSize: '13px',
                  border: '1px solid #333',
                  borderRadius: '6px',
                  backgroundColor: '#1a1a1a',
                  color: '#fff',
                  outline: 'none'
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 关键词云内容区域 */}
      <div style={{
        flex: 1,
        padding: '16px',
        overflowY: 'auto'
      }}>
        {/* 关键词云标题 */}
        <div style={{
          marginBottom: '16px',
          paddingBottom: '12px',
          borderBottom: '1px solid #333'
        }}>
          <h4 style={{ 
            margin: '0 0 4px 0', 
            fontSize: '16px', 
            color: '#fff',
            fontWeight: '600'
          }}>
            Keywords Cloud
          </h4>
          <div style={{ fontSize: '12px', color: '#a1a1aa' }}>
            {keywords.length} keywords • Click to remove
          </div>
        </div>

        {/* 关键词显示区域 */}
        <div style={{
          marginBottom: '20px',
          minHeight: '100px'
        }}>
          {keywords.length === 0 ? (
            <div style={{
              textAlign: 'center',
              color: '#6b7280',
              fontSize: '13px',
              padding: '20px'
            }}>
              No keywords available
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {Object.keys(levelNames).map(level => {
                const levelKeywords = keywords.filter(k => k.level === level);
                if (levelKeywords.length === 0) return null;
                
                return (
                  <div key={level}>
                    {/* 层级标题 */}
                    <div style={{
                      fontSize: '12px',
                      fontWeight: '600',
                      color: levelColors[level as keyof typeof levelColors],
                      marginBottom: '8px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px'
                    }}>
                      {levelNames[level as keyof typeof levelNames]} ({levelKeywords.length})
                    </div>
                    
                    {/* 该层级的关键词 */}
                    <div style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '6px',
                      marginBottom: '4px'
                    }}>
                      {levelKeywords.map((keyword, index) => {
                        const globalIndex = keywords.findIndex(k => k === keyword);
                        return (
                          <div
                            key={globalIndex}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '4px 8px',
                              backgroundColor: keyword.color + '15',
                              border: `1px solid ${keyword.color}30`,
                              borderRadius: '12px',
                              fontSize: '12px',
                              color: keyword.color,
                              cursor: 'pointer',
                              transition: 'all 0.2s',
                              userSelect: 'none'
                            }}
                            onClick={() => removeKeyword(globalIndex)}
                            title={`Click to remove`}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = keyword.color + '25';
                              e.currentTarget.style.borderColor = keyword.color + '50';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = keyword.color + '15';
                              e.currentTarget.style.borderColor = keyword.color + '30';
                            }}
                          >
                            <span>{keyword.term}</span>
                            <span style={{ fontSize: '10px', opacity: 0.7 }}>×</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })
              }
              
              {/* 自定义关键词单独显示 */}
              {(() => {
                const customKeywords = keywords.filter(k => k.level === 'custom');
                if (customKeywords.length === 0) return null;
                
                return (
                  <div>
                    <div style={{
                      fontSize: '12px',
                      fontWeight: '600',
                      color: '#6366f1',
                      marginBottom: '8px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px'
                    }}>
                      CUSTOM KEYWORDS ({customKeywords.length})
                    </div>
                    
                    <div style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '6px'
                    }}>
                      {customKeywords.map((keyword, index) => {
                        const globalIndex = keywords.findIndex(k => k === keyword);
                        return (
                          <div
                            key={globalIndex}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '4px 8px',
                              backgroundColor: '#6366f115',
                              border: '1px solid #6366f130',
                              borderRadius: '12px',
                              fontSize: '12px',
                              color: '#6366f1',
                              cursor: 'pointer',
                              transition: 'all 0.2s',
                              userSelect: 'none'
                            }}
                            onClick={() => removeKeyword(globalIndex)}
                            title="Click to remove"
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = '#6366f125';
                              e.currentTarget.style.borderColor = '#6366f150';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = '#6366f115';
                              e.currentTarget.style.borderColor = '#6366f130';
                            }}
                          >
                            <span>{keyword.term}</span>
                            <span style={{ fontSize: '10px', opacity: 0.7 }}>×</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()
              }
            </div>
          )}
        </div>

        {/* 添加自定义关键词 */}
        <div style={{ marginBottom: '20px' }}>
          <div style={{
            display: 'flex',
            gap: '8px',
            marginBottom: '8px'
          }}>
            <input
              type="text"
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && addCustomKeyword()}
              placeholder="Add custom keyword..."
              style={{
                flex: 1,
                padding: '8px 12px',
                fontSize: '13px',
                border: '1px solid #333',
                borderRadius: '6px',
                backgroundColor: '#1a1a1a',
                color: '#fff',
                outline: 'none'
              }}
            />
            <button
              onClick={addCustomKeyword}
              style={{
                padding: '8px 16px',
                fontSize: '13px',
                border: '1px solid #3bb0e6',
                borderRadius: '6px',
                backgroundColor: 'rgba(59,176,230,0.1)',
                color: '#3bb0e6',
                cursor: 'pointer',
                fontWeight: '600'
              }}
            >
              Add
            </button>
          </div>
        </div>

        {/* 搜索按钮 */}
        <div style={{ marginTop: 'auto' }}>
          <button
            onClick={handleSearch}
            disabled={isLoading || keywords.length === 0}
            style={{
              width: '100%',
              padding: '12px',
              fontSize: '14px',
              fontWeight: '600',
              border: 'none',
              borderRadius: '8px',
              backgroundColor: keywords.length > 0 && !isLoading ? '#10b981' : '#666',
              color: '#fff',
              cursor: keywords.length > 0 && !isLoading ? 'pointer' : 'not-allowed',
              transition: 'all 0.2s',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px'
            }}
          >
            {isLoading ? (
              <>
                <span>Searching...</span>
                <div style={{
                  width: '16px',
                  height: '16px',
                  border: '2px solid rgba(255,255,255,0.3)',
                  borderTop: '2px solid #fff',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite'
                }}></div>
              </>
            ) : (
              <>
                <span>Search Papers</span>
              </>
            )}
          </button>
        </div>
      </div>

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