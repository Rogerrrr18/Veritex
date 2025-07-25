"""
学科检测模块 - 智能识别研究领域并提供专业术语扩展
为不同学科提供针对性的关键词扩展策略
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Discipline:
    """学科信息"""
    name: str
    chinese_name: str
    keywords: List[str]
    synonyms: Dict[str, List[str]]
    common_terms: List[str]

class DisciplineDetector:
    """学科检测器"""
    
    def __init__(self):
        self.disciplines = self._initialize_disciplines()
        
    def _initialize_disciplines(self) -> Dict[str, Discipline]:
        """初始化学科数据库"""
        
        disciplines = {}
        
        # 化学工程
        disciplines['chemical_engineering'] = Discipline(
            name='chemical_engineering',
            chinese_name='化学工程',
            keywords=[
                'catalyst', 'catalysis', 'reaction', 'reactor', 'chemical process',
                'reforming', 'synthesis', 'separation', 'distillation', 'crystallization',
                'mass transfer', 'heat transfer', 'thermodynamics', 'kinetics',
                'methane', 'ethylene', 'propylene', 'benzene', 'toluene',
                'petroleum', 'refinery', 'petrochemical', 'polymer', 'polymerization'
            ],
            synonyms={
                'catalyst': ['catalytic', 'heterogeneous catalyst', 'homogeneous catalyst', 'biocatalyst'],
                'reforming': ['steam reforming', 'dry reforming', 'partial oxidation', 'autothermal reforming'],
                'methane': ['CH4', 'natural gas', 'biogas'],
                'synthesis': ['synthetic', 'production', 'manufacturing'],
                'reaction': ['reactive', 'chemical reaction', 'reaction mechanism']
            },
            common_terms=[
                'process optimization', 'reaction engineering', 'process design',
                'industrial chemistry', 'chemical plant', 'process control'
            ]
        )
        
        # 生物医学
        disciplines['biomedical'] = Discipline(
            name='biomedical',
            chinese_name='生物医学',
            keywords=[
                'cancer', 'tumor', 'oncology', 'therapy', 'treatment', 'drug',
                'protein', 'gene', 'DNA', 'RNA', 'cell', 'molecular',
                'clinical', 'patient', 'disease', 'diagnosis', 'biomarker',
                'immunology', 'pharmacology', 'biochemistry', 'genetics',
                'stem cell', 'tissue engineering', 'regenerative medicine'
            ],
            synonyms={
                'cancer': ['oncology', 'tumor', 'carcinoma', 'malignancy', 'neoplasm'],
                'treatment': ['therapy', 'therapeutic', 'intervention', 'medication'],
                'drug': ['pharmaceutical', 'medicine', 'compound', 'agent'],
                'protein': ['peptide', 'amino acid', 'enzyme'],
                'gene': ['genetic', 'genomic', 'allele', 'mutation']
            },
            common_terms=[
                'clinical trial', 'in vitro', 'in vivo', 'molecular biology',
                'cell culture', 'bioassay', 'immunoassay'
            ]
        )
        
        # 计算机科学
        disciplines['computer_science'] = Discipline(
            name='computer_science',
            chinese_name='计算机科学',
            keywords=[
                'algorithm', 'machine learning', 'artificial intelligence', 'neural network',
                'deep learning', 'computer vision', 'natural language processing',
                'data mining', 'big data', 'database', 'software', 'programming',
                'distributed system', 'cloud computing', 'cybersecurity',
                'blockchain', 'quantum computing', 'robotics', 'automation'
            ],
            synonyms={
                'machine learning': ['ML', 'artificial intelligence', 'AI', 'data science'],
                'neural network': ['deep learning', 'CNN', 'RNN', 'transformer'],
                'algorithm': ['algorithmic', 'computational', 'optimization'],
                'database': ['data management', 'data storage', 'SQL'],
                'programming': ['software development', 'coding', 'software engineering']
            },
            common_terms=[
                'computational complexity', 'data structure', 'software architecture',
                'system design', 'performance optimization'
            ]
        )
        
        # 材料科学
        disciplines['materials_science'] = Discipline(
            name='materials_science',
            chinese_name='材料科学',
            keywords=[
                'material', 'nanomaterial', 'nanoparticle', 'composite', 'polymer',
                'ceramic', 'metal', 'alloy', 'crystal', 'semiconductor',
                'thin film', 'coating', 'surface', 'characterization',
                'mechanical properties', 'electrical properties', 'thermal properties',
                'synthesis', 'fabrication', 'processing'
            ],
            synonyms={
                'nanomaterial': ['nanostructure', 'nanocomposite', 'nanotechnology'],
                'polymer': ['plastic', 'macromolecule', 'resin'],
                'metal': ['metallic', 'alloy', 'intermetallic'],
                'synthesis': ['preparation', 'fabrication', 'production'],
                'characterization': ['analysis', 'measurement', 'testing']
            },
            common_terms=[
                'microstructure', 'phase transition', 'crystal structure',
                'material properties', 'performance evaluation'
            ]
        )
        
        # 物理学
        disciplines['physics'] = Discipline(
            name='physics',
            chinese_name='物理学',
            keywords=[
                'quantum', 'photon', 'electron', 'laser', 'optics', 'spectroscopy',
                'magnetic', 'electromagnetic', 'superconductor', 'plasma',
                'particle', 'radiation', 'nuclear', 'atomic', 'molecular',
                'thermodynamics', 'mechanics', 'relativity', 'field theory',
                'condensed matter', 'solid state'
            ],
            synonyms={
                'quantum': ['quantum mechanics', 'quantum physics', 'quantum theory'],
                'laser': ['optical', 'photonic', 'light'],
                'magnetic': ['magnetism', 'ferromagnetic', 'diamagnetic'],
                'particle': ['subatomic', 'elementary particle'],
                'nuclear': ['atomic nucleus', 'radioactive', 'isotope']
            },
            common_terms=[
                'theoretical physics', 'experimental physics', 'applied physics',
                'quantum field theory', 'statistical mechanics'
            ]
        )
        
        return disciplines
    
    def detect(self, query: str) -> Tuple[str, float]:
        """
        检测查询属于哪个学科
        
        Args:
            query: 搜索查询字符串
            
        Returns:
            Tuple[学科名称, 置信度]
        """
        query_lower = query.lower()
        scores = {}
        
        for discipline_id, discipline in self.disciplines.items():
            score = 0.0
            
            # 检查关键词匹配
            for keyword in discipline.keywords:
                if keyword.lower() in query_lower:
                    score += 1.0
            
            # 检查同义词匹配
            for main_term, synonyms in discipline.synonyms.items():
                if main_term.lower() in query_lower:
                    score += 1.5  # 主要术语权重更高
                for synonym in synonyms:
                    if synonym.lower() in query_lower:
                        score += 1.0
            
            # 检查常用术语
            for term in discipline.common_terms:
                if term.lower() in query_lower:
                    score += 0.5
            
            scores[discipline_id] = score
        
        # 找到得分最高的学科
        if scores:
            best_discipline = max(scores.items(), key=lambda x: x[1])
            discipline_name = best_discipline[0]
            confidence = min(best_discipline[1] / 3.0, 1.0)  # 标准化置信度
            
            if confidence > 0.1:  # 最低置信度阈值
                return discipline_name, confidence
        
        # 如果没有明确匹配，返回通用学科
        return 'general', 0.0
    
    def get_discipline_info(self, discipline_name: str) -> Optional[Discipline]:
        """获取学科信息"""
        return self.disciplines.get(discipline_name)
    
    def get_domain_synonyms(self, query: str, discipline_name: str) -> List[str]:
        """获取领域特定的同义词扩展"""
        discipline = self.get_discipline_info(discipline_name)
        if not discipline:
            return []
        
        query_terms = query.lower().split()
        expanded_terms = []
        
        # 查找同义词
        for term in query_terms:
            for main_term, synonyms in discipline.synonyms.items():
                if term in main_term.lower() or main_term.lower() in term:
                    expanded_terms.extend(synonyms)
                elif term in [s.lower() for s in synonyms]:
                    expanded_terms.append(main_term)
                    expanded_terms.extend([s for s in synonyms if s.lower() != term])
        
        # 添加相关的常用术语
        for common_term in discipline.common_terms:
            # 如果查询与常用术语有词汇重叠，添加整个短语
            common_words = set(common_term.lower().split())
            query_words = set(query_terms)
            if common_words.intersection(query_words):
                expanded_terms.append(common_term)
        
        # 去重并返回
        return list(set(expanded_terms))
    
    def get_chinese_discipline_name(self, discipline_name: str) -> str:
        """获取学科的中文名称"""
        discipline = self.get_discipline_info(discipline_name)
        return discipline.chinese_name if discipline else '通用'
    
    def expand_with_discipline_context(self, query: str) -> Dict[str, any]:
        """
        基于学科上下文扩展查询
        
        Returns:
            Dict包含原查询、检测到的学科、扩展术语等信息
        """
        discipline_name, confidence = self.detect(query)
        discipline_info = self.get_discipline_info(discipline_name)
        
        result = {
            'original_query': query,
            'detected_discipline': discipline_name,
            'discipline_chinese': self.get_chinese_discipline_name(discipline_name),
            'confidence': confidence,
            'expanded_terms': [],
            'discipline_context': []
        }
        
        if discipline_info:
            # 获取领域特定的同义词
            domain_synonyms = self.get_domain_synonyms(query, discipline_name)
            result['expanded_terms'] = domain_synonyms
            
            # 添加学科上下文信息
            result['discipline_context'] = discipline_info.common_terms[:5]  # 限制数量
        
        return result

# 使用示例
def main():
    """测试学科检测功能"""
    detector = DisciplineDetector()
    
    test_queries = [
        "甲烷干重整催化剂",
        "machine learning algorithms",
        "cancer treatment methods",
        "nanomaterial synthesis",
        "quantum computing applications",
        "protein folding dynamics"
    ]
    
    for query in test_queries:
        result = detector.expand_with_discipline_context(query)
        
        print(f"\n查询: {query}")
        print(f"检测学科: {result['discipline_chinese']} ({result['detected_discipline']})")
        print(f"置信度: {result['confidence']:.2f}")
        print(f"扩展术语: {result['expanded_terms'][:5]}")  # 显示前5个
        print(f"学科上下文: {result['discipline_context'][:3]}")  # 显示前3个

if __name__ == "__main__":
    main()