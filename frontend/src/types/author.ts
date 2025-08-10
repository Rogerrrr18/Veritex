/**
 * 作者分析相关的TypeScript类型定义
 * 与后端API接口保持一致
 */

// 作者基本信息
export interface Author {
  id: string
  name: string
  display_name: string
  orcid?: string
  institutions: string[]
  research_areas: string[]
  works_count: number
  cited_by_count: number
  h_index?: number
  i10_index?: number
  homepage_url?: string
  image_url?: string
}

// 作者作品
export interface AuthorWork {
  id: string
  title: string
  authors: string[]
  publication_year?: number
  journal: string
  doi?: string
  citation_count: number
  is_open_access: boolean
  type: string
  abstract?: string
  url?: string
}

// 合作者信息
export interface Collaborator {
  author: Author
  collaboration_count: number
}

// 合作网络
export interface CollaborationNetwork {
  primary_author: Author
  collaborators: Collaborator[]
  collaboration_strength: { [authorId: string]: number }
  common_institutions: string[]
  research_overlap_areas: string[]
  network_size: number
}

// 研究轨迹 - 年度统计
export interface YearlyStats {
  publication_count: number
  total_citations: number
  journals: string[]
  collaboration_count: number
}

// 研究轨迹
export interface ResearchTrajectory {
  yearly_statistics: { [year: string]: YearlyStats }
  research_evolution: { [year: string]: string[] }
  career_span: number
  total_publications: number
  total_citations: number
  average_citations_per_paper: number
}

// API响应类型
export interface AuthorSearchResponse {
  success: boolean
  data: {
    authors: Author[]
    total_found: number
    query: string
    filters: {
      institution?: string
      research_topic?: string
    }
  }
  error?: string
}

export interface AuthorProfileResponse {
  success: boolean
  data: {
    author: Author
  }
  error?: string
}

export interface AuthorWorksResponse {
  success: boolean
  data: {
    works: AuthorWork[]
    total_found: number
    filters: {
      publication_type?: string
      min_citations?: number
    }
  }
  error?: string
}

export interface CollaborationResponse {
  success: boolean
  data: CollaborationNetwork
  error?: string
}

export interface TrajectoryResponse {
  success: boolean
  data: {
    trajectory: ResearchTrajectory
    author_id: string
  }
  error?: string
}

// 搜索过滤器
export interface AuthorSearchFilters {
  institution?: string
  researchTopic?: string
  limit?: number
}

export interface WorksSearchFilters {
  publicationType?: string
  minCitations?: number
  limit?: number
}

// UI状态类型
export interface AuthorSearchState {
  query: string
  filters: AuthorSearchFilters
  results: Author[]
  loading: boolean
  error: string
  totalFound: number
}

export interface AuthorDetailState {
  author: Author | null
  works: AuthorWork[]
  trajectory: ResearchTrajectory | null
  collaboration: CollaborationNetwork | null
  loading: {
    profile: boolean
    works: boolean
    trajectory: boolean
    collaboration: boolean
  }
  error: {
    profile: string
    works: string
    trajectory: string
    collaboration: string
  }
}

// 图表数据类型（用于可视化）
export interface ChartDataPoint {
  year: number
  publications: number
  citations: number
  collaborations: number
}

export interface NetworkNode {
  id: string
  name: string
  group: number
  value: number
  institutions: string[]
}

export interface NetworkLink {
  source: string
  target: string
  value: number
}

export interface NetworkData {
  nodes: NetworkNode[]
  links: NetworkLink[]
}