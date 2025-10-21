import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../config';
import { UserStorage, USER_DATA_KEYS } from '../utils/userStorage';

interface HierarchicalKeywords {
  exact_terms?: {
    chinese?: string[];
    english?: string[];
    weight: number;
  };
  core_synonyms?: {
    chinese?: string[];
    english?: string[];
    weight: number;
  };
  related_terms?: {
    chinese?: string[];
    english?: string[];
    weight: number;
  };
  context_terms?: {
    chinese?: string[];
    english?: string[];
    weight: number;
  };
}

interface KeywordCloudWidgetProps {
  hierarchicalKeywords: HierarchicalKeywords | null;
  originalQuery?: string;
  isDraggable?: boolean;
  theme?: 'light' | 'dark';
}

interface SearchSettings {
  maxResults: number;
  yearFrom: string;
  yearTo: string;
  sources: string[];
  useChinese?: boolean; // 新增：是否使用中文模式
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
  theme = 'dark'
}) => {
  const navigate = useNavigate();
  const [keywords, setKeywords] = useState<KeywordItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [newKeyword, setNewKeyword] = useState('');
  
  // 🔑 关键词云数据持久化状态
  const [keywordCloudData, setKeywordCloudData] = useState<{
    hierarchicalKeywords: HierarchicalKeywords | null;
    expandedKeywords: KeywordItem[];
    originalQuery?: string;
  } | null>(() => {
    // 尝试从存储中恢复关键词云数据
    try {
      const savedData = UserStorage.getUserData(USER_DATA_KEYS.KEYWORD_CLOUD);
      if (savedData) {
        const parsed = JSON.parse(savedData);
        console.log('🔍 页面初始化-恢复关键词云数据:', parsed);
        console.log('🔍 数据包含层级:', Object.keys(parsed.hierarchicalKeywords || {}));
        return parsed;
      } else {
        console.log('📭 页面初始化-未找到存储的关键词云数据');
      }
    } catch (error) {
      console.warn('⚠️ 恢复关键词云数据失败:', error);
    }
    return null;
  });
  
  const [displayChinese, setDisplayChinese] = useState(() => {
    // 恢复语言偏好
    const savedLanguage = UserStorage.getUserData('language_preference');
    const isChinese = savedLanguage === 'chinese';
    console.log('🔍 KeywordCloudWidget初始化:', { savedLanguage, isChinese, hierarchicalKeywords: !!hierarchicalKeywords, hasStoredData: !!keywordCloudData });
    return isChinese;
  }); // 新增：控制显示中文还是英文，支持持久化
  const [searchSettings, setSearchSettings] = useState<SearchSettings>(() => {
    // 优先恢复已保存的用户搜索设置
    try {
      const saved = UserStorage.getUserData(USER_DATA_KEYS.USER_SETTINGS);
      const savedLanguage = UserStorage.getUserData('language_preference');
      const isChinese = savedLanguage === 'chinese';
      if (saved) {
        const parsed = JSON.parse(saved);
        return {
          maxResults: Number(parsed.maxResults) || 20,
          yearFrom: typeof parsed.yearFrom === 'string' ? parsed.yearFrom : (parsed.yearFrom ? String(parsed.yearFrom) : ''),
          yearTo: typeof parsed.yearTo === 'string' ? parsed.yearTo : (parsed.yearTo ? String(parsed.yearTo) : ''),
          sources: Array.isArray(parsed.sources) && parsed.sources.length > 0 ? parsed.sources : ['scholarly'],
          useChinese: typeof parsed.useChinese === 'boolean' ? parsed.useChinese : isChinese
        }
      }
      return {
        maxResults: 20,
        yearFrom: '',
        yearTo: '',
        sources: ['scholarly'], // 默认只选择Google Scholar
        useChinese: isChinese
      };
    } catch {
      // 降级到默认配置
      const savedLanguage = UserStorage.getUserData('language_preference');
      const isChinese = savedLanguage === 'chinese';
      return {
        maxResults: 20,
        yearFrom: '',
        yearTo: '',
        sources: ['scholarly'],
        useChinese: isChinese
      };
    }
  });

  // 持久化搜索设置，供聊天模式读取
  useEffect(() => {
    try {
      const toSave = {
        maxResults: searchSettings.maxResults,
        yearFrom: searchSettings.yearFrom,
        yearTo: searchSettings.yearTo,
        sources: searchSettings.sources,
        useChinese: searchSettings.useChinese
      };
      UserStorage.setUserData(USER_DATA_KEYS.USER_SETTINGS, JSON.stringify(toSave));
    } catch (e) {
      console.warn('⚠️ 保存搜索设置失败:', e);
    }
  }, [searchSettings]);

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

  // 🔑 保存关键词云数据到存储
  const saveKeywordCloudData = (data: {
    hierarchicalKeywords: HierarchicalKeywords | null;
    expandedKeywords: KeywordItem[];
    originalQuery?: string;
  }) => {
    try {
      UserStorage.setUserData(USER_DATA_KEYS.KEYWORD_CLOUD, JSON.stringify(data));
      setKeywordCloudData(data);
      console.log('💾 关键词云数据已保存:', data);
    } catch (error) {
      console.warn('⚠️ 保存关键词云数据失败:', error);
    }
  };
  
  // 🗑️ 清除关键词云数据
  const clearKeywordCloudData = () => {
    console.log('🗑️ 用户手动清除关键词云数据');
    UserStorage.removeUserData(USER_DATA_KEYS.KEYWORD_CLOUD);
    setKeywordCloudData(null);
    setKeywords([]);
    console.log('✅ 关键词云数据已清除完毕');
  };

  // 🔄 优先使用存储的数据，其次使用传入的数据
  const activeHierarchicalKeywords = hierarchicalKeywords || keywordCloudData?.hierarchicalKeywords;
  const activeOriginalQuery = (hierarchicalKeywords ? undefined : keywordCloudData?.originalQuery) || '';

  // 解析层次化关键词数据
  useEffect(() => {
    const currentHierarchicalKeywords = activeHierarchicalKeywords;
    
    // 🔧 优化数据来源检测和日志记录
    if (hierarchicalKeywords) {
      console.log('🔍 使用新传入的关键词数据:', hierarchicalKeywords);
    } else if (keywordCloudData?.hierarchicalKeywords) {
      console.log('🔄 使用存储的关键词数据:', keywordCloudData.hierarchicalKeywords);
    } else {
      console.log('❌ 没有可用的关键词数据 - 显示空状态');
      setKeywords([]);
      return;
    }
    
    if (!currentHierarchicalKeywords) {
      console.log('❌ 当前活跃关键词数据为空');
      setKeywords([]);
      return;
    }

    const newKeywords: KeywordItem[] = [];

    // 🔧 新增：支持双语关键词解析
    try {
      // 按层级处理关键词 - 使用当前活跃的关键词数据
      Object.entries(currentHierarchicalKeywords).forEach(([level, data]) => {
        if (data && typeof data === 'object') {
          // 根据displayChinese状态选择显示的语言
          const termsToDisplay = displayChinese 
            ? (data.chinese || data.english || [])  // 中文模式：优先中文，降级英文
            : (data.english || data.chinese || []); // 英文模式：优先英文，降级中文
          
          if (Array.isArray(termsToDisplay)) {
            termsToDisplay.forEach((term: string) => {
              if (term && typeof term === 'string' && term.trim()) {
                newKeywords.push({
                  term: term.trim(),
                  level,
                  weight: typeof data.weight === 'number' ? data.weight : 1.0,
                  color: levelColors[level as keyof typeof levelColors] || '#6b7280'
                });
              }
            });
          }
        } else {
          console.warn(`⚠️ 关键词层级 ${level} 的数据格式异常:`, data);
        }
      });

      setKeywords(newKeywords);
      console.log(`✅ 成功解析 ${newKeywords.length} 个关键词 (${displayChinese ? '中文' : '英文'}模式)`);
      
      // 🔑 只有当有新传入的数据时才保存到存储（避免重复保存）
      if (hierarchicalKeywords) {
        console.log('💾 检测到新的关键词数据，保存到存储');
        saveKeywordCloudData({
          hierarchicalKeywords,
          expandedKeywords: newKeywords,
          originalQuery: activeOriginalQuery
        });
      } else if (keywordCloudData && newKeywords.length > 0) {
        // 如果是从存储恢复的数据，确保当前显示的关键词与存储保持同步
        console.log('🔄 从存储恢复数据，更新显示的关键词');
        const updatedData = {
          ...keywordCloudData,
          expandedKeywords: newKeywords
        };
        setKeywordCloudData(updatedData);
        // 静默更新存储（不打印保存日志）
        try {
          UserStorage.setUserData(USER_DATA_KEYS.KEYWORD_CLOUD, JSON.stringify(updatedData));
        } catch (error) {
          console.warn('⚠️ 更新关键词显示数据失败:', error);
        }
      }
    } catch (error) {
      console.error('❌ 解析关键词数据时出错:', error);
      console.error('异常的关键词数据:', currentHierarchicalKeywords);
      setKeywords([]); // 出错时清空关键词
    }
  }, [hierarchicalKeywords, keywordCloudData, displayChinese, activeHierarchicalKeywords, activeOriginalQuery]); // 优化依赖项

  // 添加自定义关键词
  const addCustomKeyword = () => {
    if (newKeyword.trim()) {
      const newKeywordItem = {
        term: newKeyword.trim(),
        level: 'custom',
        weight: 1.0,
        color: '#6366f1',
        editable: true
      };
      
      const updatedKeywords = [...keywords, newKeywordItem];
      setKeywords(updatedKeywords);
      setNewKeyword('');
      
      // 🔑 保存更新后的关键词云数据
      saveKeywordCloudData({
        hierarchicalKeywords: activeHierarchicalKeywords || null,
        expandedKeywords: updatedKeywords,
        originalQuery: activeOriginalQuery
      });
    }
  };

  // 删除关键词
  const removeKeyword = (index: number) => {
    const updatedKeywords = keywords.filter((_, i) => i !== index);
    setKeywords(updatedKeywords);
    
    // 🔑 保存更新后的关键词云数据
    saveKeywordCloudData({
      hierarchicalKeywords: activeHierarchicalKeywords || null,
      expandedKeywords: updatedKeywords,
      originalQuery: activeOriginalQuery
    });
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

      // 🔑 关键优化：构建预扩展关键词，支持双语模式
      const preExpandedKeywords = {
        hierarchical_keywords: {
          exact_terms: {
            chinese: keywords.filter(k => k.level === 'exact_terms').map(k => k.term),
            english: keywords.filter(k => k.level === 'exact_terms').map(k => k.term),
            weight: 1.0
          },
          core_synonyms: {
            chinese: keywords.filter(k => k.level === 'core_synonyms').map(k => k.term),
            english: keywords.filter(k => k.level === 'core_synonyms').map(k => k.term),
            weight: 0.9
          },
          related_terms: {
            chinese: keywords.filter(k => k.level === 'related_terms').map(k => k.term),
            english: keywords.filter(k => k.level === 'related_terms').map(k => k.term),
            weight: 0.5
          },
          context_terms: {
            chinese: keywords.filter(k => k.level === 'context_terms').map(k => k.term),
            english: keywords.filter(k => k.level === 'context_terms').map(k => k.term),
            weight: 0.4
          }
        },
        domain: 'academic_research',
        core_concepts: keywords.map(k => k.term),
        useChinese: searchSettings.useChinese // 🔑 添加中文模式标识
      };

      console.log('🚀 使用预扩展关键词执行搜索，避免重复LLM分析');
      console.log('📊 预扩展关键词结构:', preExpandedKeywords);

      // 调用搜索API，传递预扩展关键词以避免重复LLM分析
      const searchResult = await api.searchPapers(
        searchQuery, 
        searchSettings.maxResults, 
        false, // enable_expansion
        searchSettings.yearFrom, 
        searchSettings.yearTo,
        preExpandedKeywords,  // 🔑 传递预扩展关键词
        searchSettings.sources, // 🔑 传递数据源选择
        searchSettings.useChinese // 🔑 新增：传递中文搜索模式参数
      );
      
      // 处理搜索结果
      const papers = searchResult.success && searchResult.data 
        ? searchResult.data.papers 
        : (searchResult.papers || []);

      // 获取Exact Terms作为标题
      const exactTerms = keywords.filter(k => k.level === 'exact_terms').map(k => k.term);
      const titleFromExactTerms = exactTerms.length > 0 ? exactTerms.join(', ') : '';
      const finalTitle = titleFromExactTerms || keywords.map(k => k.term).slice(0, 3).join(', ') || 'Keywords Search';

      // 创建搜索历史记录
      const searchHistory = {
        id: Date.now().toString(),
        timestamp: Date.now(),
        originalQuery: finalTitle,
        expandedKeywords: keywords.map(k => k.term),
        papers: papers,
        maxResults: searchSettings.maxResults
      };

      // 保存搜索历史到用户隔离存储
      const SEARCH_STORAGE_KEY = USER_DATA_KEYS.SEARCH_HISTORY;
      const UNIFIED_HISTORY_KEY = USER_DATA_KEYS.UNIFIED_HISTORY;
      
      // 保存到搜索历史
      const existingSearchHistory = JSON.parse(UserStorage.getUserData(SEARCH_STORAGE_KEY) || '[]');
      existingSearchHistory.unshift(searchHistory);
      if (existingSearchHistory.length > 50) {
        existingSearchHistory.splice(50);
      }
      UserStorage.setUserData(SEARCH_STORAGE_KEY, JSON.stringify(existingSearchHistory));
      
      // 保存到统一历史（My面板）
      const unifiedItem = {
        id: searchHistory.id,
        timestamp: searchHistory.timestamp,
        type: 'search' as const,
        title: finalTitle.length > 50 ? finalTitle.slice(0, 50) + '...' : finalTitle,
        data: searchHistory
      };
      
      const existingUnifiedHistory = JSON.parse(UserStorage.getUserData(UNIFIED_HISTORY_KEY) || '[]');
      existingUnifiedHistory.unshift(unifiedItem);
      existingUnifiedHistory.sort((a: any, b: any) => b.timestamp - a.timestamp);
      
      if (existingUnifiedHistory.length > 100) {
        existingUnifiedHistory.splice(100);
      }
      UserStorage.setUserData(UNIFIED_HISTORY_KEY, JSON.stringify(existingUnifiedHistory));
      
      console.log('✅ 关键词搜索结果已保存到用户隔离存储和My面板');

      // 跳转到报告页面
      navigate('/report', {
        state: {
          papers,
          searchHistory,
          expandedKeywords: keywords.map(k => k.term),
          originalQuery: finalTitle,
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
        backgroundColor: theme === 'dark' ? '#0a0a0a' : '#fefcf3'
      }}>
        {/* 搜索参数设置区域 */}
        <div style={{
          padding: '16px',
          backgroundColor: theme === 'dark' ? '#111' : '#f5f3ea',
          borderBottom: '1px solid #333'
        }}>
          <h4 style={{ 
            margin: '0 0 12px 0', 
            fontSize: '14px', 
            color: theme === 'dark' ? '#fff' : '#1f2937',
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
                color: theme === 'dark' ? '#a1a1aa' : '#6b7280', 
                marginBottom: '4px' 
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
                  padding: '6px 8px',
                  fontSize: '13px',
                  border: theme === 'dark' ? '1px solid #333' : '1px solid #d6d3d1',
                  borderRadius: '6px',
                  backgroundColor: theme === 'dark' ? '#1a1a1a' : '#f7f5eb',
                  color: theme === 'dark' ? '#fff' : '#1f2937',
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
                  color: theme === 'dark' ? '#a1a1aa' : '#6b7280', 
                  marginBottom: '4px' 
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
                    border: theme === 'dark' ? '1px solid #333' : '1px solid #d6d3d1',
                    borderRadius: '6px',
                    backgroundColor: theme === 'dark' ? '#1a1a1a' : '#f7f5eb',
                    color: theme === 'dark' ? '#fff' : '#1f2937',
                    outline: 'none'
                  }}
                />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ 
                  display: 'block', 
                  fontSize: '12px', 
                  color: theme === 'dark' ? '#a1a1aa' : '#6b7280', 
                  marginBottom: '4px' 
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
                    border: theme === 'dark' ? '1px solid #333' : '1px solid #d6d3d1',
                    borderRadius: '6px',
                    backgroundColor: theme === 'dark' ? '#1a1a1a' : '#f7f5eb',
                    color: theme === 'dark' ? '#fff' : '#1f2937',
                    outline: 'none'
                  }}
                />
              </div>
            </div>
            
            {/* 数据源选择 - 带右上角语言开关的面板 */}
            <div>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '6px'
              }}>
                <label style={{ 
                  fontSize: '12px', 
                  color: theme === 'dark' ? '#a1a1aa' : '#6b7280',
                  margin: 0
                }}>
                  Data Sources
                </label>
                
                {/* 现代开关样式的语言切换 */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <span style={{
                    fontSize: '10px',
                    color: theme === 'dark' ? '#a1a1aa' : '#6b7280',
                    fontWeight: '500'
                  }}>
                    En
                  </span>
                  <div 
                    onClick={() => {
                      const newDisplayChinese = !displayChinese;
                      setDisplayChinese(newDisplayChinese);
                      setSearchSettings(prev => ({
                        ...prev,
                        useChinese: newDisplayChinese
                      }));
                      // 保存语言偏好到持久化存储
                      UserStorage.setUserData('language_preference', newDisplayChinese ? 'chinese' : 'english');
                    }}
                    style={{
                      width: '32px',
                      height: '16px',
                      borderRadius: '8px',
                      backgroundColor: displayChinese ? '#10b981' : '#f59e0b', // 中文绿色，英文黄色
                      cursor: 'pointer',
                      position: 'relative',
                      transition: 'all 0.2s ease',
                      border: '1px solid ' + (displayChinese ? '#10b981' : '#f59e0b') // 边框颜色也相应调整
                    }}
                    title={displayChinese ? '切换到英文关键词模式' : '切换到中文关键词模式'}
                  >
                    <div style={{
                      width: '12px',
                      height: '12px',
                      borderRadius: '6px',
                      backgroundColor: '#ffffff',
                      position: 'absolute',
                      top: '1px',
                      left: displayChinese ? '17px' : '1px',
                      transition: 'all 0.2s ease',
                      boxShadow: '0 1px 2px rgba(0, 0, 0, 0.2)'
                    }} />
                  </div>
                  <span style={{
                    fontSize: '10px',
                    color: theme === 'dark' ? '#a1a1aa' : '#6b7280',
                    fontWeight: '500'
                  }}>
                    中
                  </span>
                </div>
              </div>
              <div style={{ 
                display: 'flex', 
                gap: '8px',
                flexWrap: 'wrap'
              }}>
                {/* Google Scholar 按钮 */}
                <button
                  onClick={() => {
                    setSearchSettings(prev => ({
                      ...prev,
                      sources: ['scholarly'] // 只选择Google Scholar
                    }));
                  }}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '6px',
                    border: searchSettings.sources.length === 1 && searchSettings.sources.includes('scholarly')
                      ? '2px solid #10b981' : '1px solid #333',
                    backgroundColor: searchSettings.sources.length === 1 && searchSettings.sources.includes('scholarly')
                      ? 'rgba(16, 185, 129, 0.2)' : (theme === 'dark' ? '#1a1a1a' : '#f7f5eb'),
                    color: searchSettings.sources.length === 1 && searchSettings.sources.includes('scholarly')
                      ? '#10b981' : (theme === 'dark' ? '#fff' : '#1f2937'),
                    cursor: 'pointer',
                    fontSize: '12px',
                    fontWeight: '600',
                    outline: 'none',
                    transition: 'all 0.2s ease'
                  }}
                >
                  Google Scholar
                </button>
                
                {/* arXiv 按钮 */}
                <button
                  onClick={() => setSearchSettings(prev => ({
                    ...prev,
                    sources: ['arxiv'] // 只选择arXiv
                  }))}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '6px',
                    border: searchSettings.sources.length === 1 && searchSettings.sources.includes('arxiv') 
                      ? '2px solid #f59e0b' : '1px solid #333',
                    backgroundColor: searchSettings.sources.length === 1 && searchSettings.sources.includes('arxiv')
                      ? 'rgba(245, 158, 11, 0.2)' : (theme === 'dark' ? '#1a1a1a' : '#f7f5eb'),
                    color: searchSettings.sources.length === 1 && searchSettings.sources.includes('arxiv')
                      ? '#f59e0b' : (theme === 'dark' ? '#fff' : '#1f2937'),
                    cursor: 'pointer',
                    fontSize: '12px',
                    fontWeight: '600',
                    outline: 'none',
                    transition: 'all 0.2s ease'
                  }}
                >
                  arXiv
                </button>
                
                {/* Crossref 按钮 */}
                <button
                  onClick={() => setSearchSettings(prev => ({
                    ...prev,
                    sources: ['crossref'] // 只选择Crossref
                  }))}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '6px',
                    border: searchSettings.sources.length === 1 && searchSettings.sources.includes('crossref') 
                      ? '2px solid #8b5cf6' : '1px solid #333',
                    backgroundColor: searchSettings.sources.length === 1 && searchSettings.sources.includes('crossref')
                      ? 'rgba(139, 92, 246, 0.2)' : (theme === 'dark' ? '#1a1a1a' : '#f7f5eb'),
                    color: searchSettings.sources.length === 1 && searchSettings.sources.includes('crossref')
                      ? '#8b5cf6' : (theme === 'dark' ? '#fff' : '#1f2937'),
                    cursor: 'pointer',
                    fontSize: '12px',
                    fontWeight: '600',
                    outline: 'none',
                    transition: 'all 0.2s ease'
                  }}
                >
                  Crossref
                </button>
              </div>
              
              {/* 显示当前选择的数据源和模式 */}
              <div style={{
                marginTop: '6px',
                fontSize: '11px',
                color: theme === 'dark' ? '#666' : '#9ca3af'
              }}>
                {searchSettings.sources.length === 1 && searchSettings.sources.includes('scholarly') ? 
                  `Google Scholar selected ${displayChinese ? '(中文模式)' : '(English mode)'}` :
                  searchSettings.sources.length === 1 && searchSettings.sources.includes('arxiv') ?
                    `arXiv selected ${displayChinese ? '(中文模式)' : '(English mode)'}` :
                    searchSettings.sources.length === 1 && searchSettings.sources.includes('crossref') ?
                      `Crossref selected ${displayChinese ? '(中文模式)' : '(English mode)'}` :
                      `${searchSettings.sources.length} sources selected ${displayChinese ? '(中文模式)' : '(English mode)'}`
                }
              </div>
            </div>
          </div>
        </div>

        <div style={{
          flex: 1,
          padding: '20px',
          textAlign: 'center',
          color: theme === 'dark' ? '#6b7280' : '#9ca3af',
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
      backgroundColor: theme === 'dark' ? '#0a0a0a' : '#fefcf3'
    }}>
      {/* 搜索参数设置区域 - 移至顶部 */}
      <div style={{
        padding: '12px',
        backgroundColor: theme === 'dark' ? '#111' : '#f5f3ea',
        borderBottom: theme === 'dark' ? '1px solid #333' : '1px solid #e5e2d9'
      }}>
        <h4 style={{ 
          margin: '0 0 8px 0', 
          fontSize: '13px', 
          color: theme === 'dark' ? '#fff' : '#1f2937',
          fontWeight: '600'
        }}>
          Search Parameters
        </h4>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {/* 论文数量 */}
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: '12px', 
              color: theme === 'dark' ? '#a1a1aa' : '#6b7280', 
              marginBottom: '4px' 
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
                padding: '6px 8px',
                fontSize: '13px',
                border: theme === 'dark' ? '1px solid #333' : '1px solid #d6d3d1',
                borderRadius: '6px',
                backgroundColor: theme === 'dark' ? '#1a1a1a' : '#f7f5eb',
                color: theme === 'dark' ? '#fff' : '#1f2937',
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
                color: theme === 'dark' ? '#a1a1aa' : '#6b7280', 
                marginBottom: '4px' 
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
                  padding: '6px 8px',
                  fontSize: '13px',
                  border: theme === 'dark' ? '1px solid #333' : '1px solid #d6d3d1',
                  borderRadius: '6px',
                  backgroundColor: theme === 'dark' ? '#1a1a1a' : '#f7f5eb',
                  color: theme === 'dark' ? '#fff' : '#1f2937',
                  outline: 'none'
                }}
              />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ 
                display: 'block', 
                fontSize: '12px', 
                color: theme === 'dark' ? '#a1a1aa' : '#6b7280', 
                marginBottom: '4px' 
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
                  padding: '6px 8px',
                  fontSize: '13px',
                  border: theme === 'dark' ? '1px solid #333' : '1px solid #d6d3d1',
                  borderRadius: '6px',
                  backgroundColor: theme === 'dark' ? '#1a1a1a' : '#f7f5eb',
                  color: theme === 'dark' ? '#fff' : '#1f2937',
                  outline: 'none'
                }}
              />
            </div>
          </div>
          
          {/* 数据源选择 - 带右上角语言开关的面板 */}
          <div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '6px'
            }}>
              <label style={{ 
                fontSize: '12px', 
                color: theme === 'dark' ? '#a1a1aa' : '#6b7280',
                margin: 0
              }}>
                Data Sources
              </label>
              
              {/* 现代开关样式的语言切换 */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <span style={{
                  fontSize: '10px',
                  color: theme === 'dark' ? '#a1a1aa' : '#6b7280',
                  fontWeight: '500'
                }}>
                  En
                </span>
                <div 
                  onClick={() => {
                    const newDisplayChinese = !displayChinese;
                    console.log('🔄 语言切换:', displayChinese, '->', newDisplayChinese);
                    setDisplayChinese(newDisplayChinese);
                    setSearchSettings(prev => ({
                      ...prev,
                      useChinese: newDisplayChinese
                    }));
                    // 保存语言偏好到持久化存储
                    UserStorage.setUserData('language_preference', newDisplayChinese ? 'chinese' : 'english');
                  }}
                  style={{
                    width: '32px',
                    height: '16px',
                    borderRadius: '8px',
                    backgroundColor: displayChinese ? '#10b981' : '#f59e0b', // 中文绿色，英文黄色
                    cursor: 'pointer',
                    position: 'relative',
                    transition: 'all 0.2s ease',
                    border: '1px solid ' + (displayChinese ? '#10b981' : '#f59e0b'), // 边框颜色也相应调整
                    // 添加调试样式，确保可见性
                    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
                    minWidth: '32px', // 确保最小宽度
                    minHeight: '16px' // 确保最小高度
                  }}
                  title={displayChinese ? '切换到英文关键词模式' : '切换到中文关键词模式'}
                >
                  <div style={{
                    width: '12px',
                    height: '12px',
                    borderRadius: '6px',
                    backgroundColor: '#ffffff',
                    position: 'absolute',
                    top: '1px',
                    left: displayChinese ? '17px' : '1px',
                    transition: 'all 0.2s ease',
                    boxShadow: '0 1px 2px rgba(0, 0, 0, 0.2)'
                  }} />
                </div>
                <span style={{
                  fontSize: '10px',
                  color: theme === 'dark' ? '#a1a1aa' : '#6b7280',
                  fontWeight: '500'
                }}>
                  中
                </span>
              </div>
            </div>
            <div style={{ 
              display: 'flex', 
              gap: '8px',
              flexWrap: 'wrap'
            }}>
                {/* Google Scholar 按钮 */}
                <button
                  onClick={() => {
                    setSearchSettings(prev => ({
                      ...prev,
                      sources: ['scholarly'] // 只选择Google Scholar
                    }));
                  }}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '6px',
                    border: searchSettings.sources.length === 1 && searchSettings.sources.includes('scholarly')
                      ? '2px solid #10b981' : '1px solid #333',
                    backgroundColor: searchSettings.sources.length === 1 && searchSettings.sources.includes('scholarly')
                      ? 'rgba(16, 185, 129, 0.2)' : (theme === 'dark' ? '#1a1a1a' : '#f7f5eb'),
                    color: searchSettings.sources.length === 1 && searchSettings.sources.includes('scholarly')
                      ? '#10b981' : (theme === 'dark' ? '#fff' : '#1f2937'),
                    cursor: 'pointer',
                    fontSize: '12px',
                    fontWeight: '600',
                    outline: 'none',
                    transition: 'all 0.2s ease'
                  }}
                >
                  Google Scholar
                </button>
              
              {/* arXiv 按钮 */}
              <button
                onClick={() => setSearchSettings(prev => ({
                  ...prev,
                  sources: ['arxiv'] // 只选择arXiv
                }))}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: searchSettings.sources.length === 1 && searchSettings.sources.includes('arxiv')
                    ? '2px solid #f59e0b' : '1px solid #333',
                  backgroundColor: searchSettings.sources.length === 1 && searchSettings.sources.includes('arxiv')
                    ? 'rgba(245, 158, 11, 0.2)' : (theme === 'dark' ? '#1a1a1a' : '#f7f5eb'),
                  color: searchSettings.sources.length === 1 && searchSettings.sources.includes('arxiv')
                    ? '#f59e0b' : (theme === 'dark' ? '#fff' : '#1f2937'),
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: '600',
                  outline: 'none',
                  transition: 'all 0.2s ease'
                }}
              >
                arXiv
              </button>
              
              {/* Crossref 按钮 */}
              <button
                onClick={() => setSearchSettings(prev => ({
                  ...prev,
                  sources: ['crossref'] // 只选择Crossref
                }))}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: searchSettings.sources.length === 1 && searchSettings.sources.includes('crossref')
                    ? '2px solid #8b5cf6' : '1px solid #333',
                  backgroundColor: searchSettings.sources.length === 1 && searchSettings.sources.includes('crossref')
                    ? 'rgba(139, 92, 246, 0.2)' : (theme === 'dark' ? '#1a1a1a' : '#f7f5eb'),
                  color: searchSettings.sources.length === 1 && searchSettings.sources.includes('crossref')
                    ? '#8b5cf6' : (theme === 'dark' ? '#fff' : '#1f2937'),
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: '600',
                  outline: 'none',
                  transition: 'all 0.2s ease'
                }}
              >
                Crossref
              </button>
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
          borderBottom: theme === 'dark' ? '1px solid #333' : '1px solid #e5e2d9',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div>
            <h4 style={{ 
              margin: '0 0 4px 0', 
              fontSize: '16px', 
              color: theme === 'dark' ? '#fff' : '#1f2937',
              fontWeight: '600'
            }}>
              Keywords Cloud
            </h4>
            <div style={{ fontSize: '12px', color: theme === 'dark' ? '#a1a1aa' : '#6b7280' }}>
              {keywords.length} keywords • Click to remove
            </div>
          </div>
          
          {/* 清除按钮 */}
          {keywords.length > 0 && (
            <button
              onClick={clearKeywordCloudData}
              style={{
                padding: '6px 12px',
                fontSize: '12px',
                border: '1px solid #ef4444',
                borderRadius: '6px',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                color: '#ef4444',
                cursor: 'pointer',
                fontWeight: '500',
                transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.2)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
              }}
              title="清除所有关键词云数据"
            >
              Clear All
            </button>
          )}
        </div>

        {/* 关键词显示区域 */}
        <div style={{
          marginBottom: '20px',
          minHeight: '100px'
        }}>
          {keywords.length === 0 ? (
            <div style={{
              textAlign: 'center',
              color: theme === 'dark' ? '#6b7280' : '#9ca3af',
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
                      marginBottom: '8px'
                    }}>
                      <div style={{
                        fontSize: '12px',
                        fontWeight: '600',
                        color: levelColors[level as keyof typeof levelColors],
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px'
                      }}>
                        {levelNames[level as keyof typeof levelNames]} ({levelKeywords.length})
                      </div>
                    </div>
                    
                    {/* 该层级的关键词和Add按钮 */}
                    <div style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '6px',
                      marginBottom: '4px'
                    }}>
                      {levelKeywords.map((keyword) => {
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
                              transition: 'all 0.2s',
                              userSelect: 'none'
                            }}
                          >
                            <span style={{ cursor: 'default' }}>{keyword.term}</span>
                            <span 
                              style={{ 
                                fontSize: '10px', 
                                opacity: 0.7,
                                cursor: 'pointer',
                                padding: '2px',
                                borderRadius: '50%',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                width: '16px',
                                height: '16px',
                                transition: 'all 0.2s'
                              }}
                              onClick={(e) => {
                                e.stopPropagation();
                                removeKeyword(globalIndex);
                              }}
                              title="点击删除"
                              onMouseEnter={(e) => {
                                e.currentTarget.style.backgroundColor = keyword.color + '30';
                                e.currentTarget.style.opacity = '1';
                              }}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.backgroundColor = 'transparent';
                                e.currentTarget.style.opacity = '0.7';
                              }}
                            >
                              ×
                            </span>
                          </div>
                        );
                      })}
                      
                      {/* Add按钮放在关键词之后 */}
                      <button
                        onClick={() => {
                          const newTerm = prompt(`添加新的${levelNames[level as keyof typeof levelNames]}关键词:`);
                          if (newTerm && newTerm.trim()) {
                            const newKeywordItem = {
                              term: newTerm.trim(),
                              level: level,
                              weight: 1.0,
                              color: levelColors[level as keyof typeof levelColors],
                              editable: true
                            };
                            
                            const updatedKeywords = [...keywords, newKeywordItem];
                            setKeywords(updatedKeywords);
                            
                            // 🔑 保存更新后的关键词云数据
                            saveKeywordCloudData({
                              hierarchicalKeywords: activeHierarchicalKeywords || null,
                              expandedKeywords: updatedKeywords,
                              originalQuery: activeOriginalQuery
                            });
                          }
                        }}
                        style={{
                          width: '24px',
                          height: '24px',
                          borderRadius: '12px',
                          border: `1px solid ${levelColors[level as keyof typeof levelColors]}`,
                          backgroundColor: levelColors[level as keyof typeof levelColors] + '15',
                          color: levelColors[level as keyof typeof levelColors],
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '12px',
                          fontWeight: '600',
                          transition: 'all 0.2s'
                        }}
                        title={`添加${levelNames[level as keyof typeof levelNames]}关键词`}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = levelColors[level as keyof typeof levelColors] + '25';
                          e.currentTarget.style.borderColor = levelColors[level as keyof typeof levelColors] + '50';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = levelColors[level as keyof typeof levelColors] + '15';
                          e.currentTarget.style.borderColor = levelColors[level as keyof typeof levelColors] + '30';
                        }}
                      >
                        +
                      </button>
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
                      {customKeywords.map((keyword) => {
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
                              transition: 'all 0.2s',
                              userSelect: 'none'
                            }}
                          >
                            <span style={{ cursor: 'default' }}>{keyword.term}</span>
                            <span 
                              style={{ 
                                fontSize: '10px', 
                                opacity: 0.7,
                                cursor: 'pointer',
                                padding: '2px',
                                borderRadius: '50%',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                width: '16px',
                                height: '16px',
                                transition: 'all 0.2s'
                              }}
                              onClick={(e) => {
                                e.stopPropagation();
                                removeKeyword(globalIndex);
                              }}
                              title="点击删除"
                              onMouseEnter={(e) => {
                                e.currentTarget.style.backgroundColor = '#6366f130';
                                e.currentTarget.style.opacity = '1';
                              }}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.backgroundColor = 'transparent';
                                e.currentTarget.style.opacity = '0.7';
                              }}
                            >
                              ×
                            </span>
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
                border: theme === 'dark' ? '1px solid #333' : '1px solid #d6d3d1',
                borderRadius: '6px',
                backgroundColor: theme === 'dark' ? '#1a1a1a' : '#f7f5eb',
                color: theme === 'dark' ? '#fff' : '#1f2937',
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
              color: theme === 'dark' ? '#fff' : '#1f2937',
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
