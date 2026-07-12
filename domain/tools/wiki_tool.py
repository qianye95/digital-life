"""
Wiki知识管理工具
让数字生命能读写用户的个人Wiki知识库
"""

import os
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any


class WikiTool:
    """Wiki知识管理工具"""
    
    def __init__(self, wiki_path: str):
        self.wiki_path = Path(wiki_path)
        if not self.wiki_path.exists():
            raise ValueError(f"Wiki路径不存在: {wiki_path}")
        
        self.index_path = self.wiki_path / "index.md"
        
    def read_index(self) -> Dict[str, Any]:
        """读取wiki索引，返回结构化的知识库概览"""
        if not self.index_path.exists():
            return {"error": "index.md不存在"}
        
        content = self.index_path.read_text(encoding='utf-8')
        
        # 解析统计信息
        stats = {}
        for line in content.split('\n'):
            if line.startswith('- 会话数:'):
                stats['sessions'] = int(line.split(':')[1].split('（')[0].strip())
            elif line.startswith('- 实体数:'):
                stats['entities'] = int(line.split(':')[1].strip())
            elif line.startswith('- 概念数:'):
                stats['concepts'] = int(line.split(':')[1].strip())
            elif line.startswith('- 项目数:'):
                stats['projects'] = int(line.split(':')[1].split('（')[0].strip())
        
        return {
            "path": str(self.wiki_path),
            "last_updated": content.split('\n')[2].split(':')[1].strip(),
            "stats": stats,
            "categories": [
                "sessions", "entities", "concepts", "projects", 
                "decisions", "outputs", "technical-deep-dives", "sources"
            ]
        }
    
    def list_files(self, category: str = None) -> List[str]:
        """列出wiki中的文件，可按分类过滤"""
        if category:
            target_path = self.wiki_path / category
            if not target_path.exists():
                return []
            return [f.stem for f in target_path.glob("*.md") if f.stem != 'index']
        
        all_files = []
        for category in ["sessions", "entities", "concepts", "projects", 
                         "decisions", "outputs", "technical-deep-dives", "sources"]:
            category_path = self.wiki_path / category
            if category_path.exists():
                files = [f"{category}/{f.stem}" for f in category_path.glob("*.md") if f.stem != 'index']
                all_files.extend(files)
        
        return all_files
    
    def read_document(self, file_path: str) -> Dict[str, Any]:
        """读取wiki文档内容"""
        full_path = self.wiki_path / file_path
        if not full_path.exists():
            # 尝试添加.md后缀
            full_path = full_path.with_suffix('.md')
        
        if not full_path.exists():
            return {"error": f"文档不存在: {file_path}"}
        
        content = full_path.read_text(encoding='utf-8')
        
        # 解析frontmatter
        metadata = {}
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    metadata = yaml.safe_load(parts[1])
                except:
                    pass
        
        return {
            "path": str(full_path.relative_to(self.wiki_path)),
            "metadata": metadata,
            "content": content
        }
    
    def create_session(self, session_title: str, content: str) -> Dict[str, Any]:
        """创建新的session文档"""
        date_str = datetime.now().strftime('%Y-%m-%d')
        filename = f"{date_str}-{session_title.lower().replace(' ', '-')}.md"
        file_path = self.wiki_path / "sessions" / filename
        
        # 生成frontmatter
        metadata = {
            "type": "session",
            "title": session_title,
            "date": date_str,
            "created": datetime.now().isoformat(),
            "tags": []
        }
        
        doc_content = f"""---
{yaml.dump(metadata, allow_unicode=True, default_flow_style=False)}---

# {session_title}

**日期**: {date_str}

## 会话内容

{content}

## 关键决策

## 后续行动
"""
        
        file_path.write_text(doc_content, encoding='utf-8')
        
        return {
            "success": True,
            "path": str(file_path.relative_to(self.wiki_path)),
            "message": f"已创建session: {session_title}"
        }
    
    def update_entity(self, entity_name: str, content: str = None) -> Dict[str, Any]:
        """创建或更新实体文档"""
        file_path = self.wiki_path / "entities" / f"{entity_name}.md"
        
        if file_path.exists():
            # 更新现有实体
            if content:
                existing = file_path.read_text(encoding='utf-8')
                file_path.write_text(existing + f"\n\n## 更新 ({datetime.now().strftime('%Y-%m-%d')})\n\n{content}", 
                                   encoding='utf-8')
            return {
                "success": True,
                "path": str(file_path.relative_to(self.wiki_path)),
                "action": "updated",
                "message": f"已更新实体: {entity_name}"
            }
        else:
            # 创建新实体
            metadata = {
                "type": "entity",
                "name": entity_name,
                "created": datetime.now().isoformat()
            }
            
            doc_content = f"""---
{yaml.dump(metadata, allow_unicode=True, default_flow_style=False)}---

# {entity_name}

## 描述

## 相关项目

## 备注
"""
            if content:
                doc_content += f"\n\n## 最新信息\n\n{content}"
            
            file_path.write_text(doc_content, encoding='utf-8')
            
            return {
                "success": True,
                "path": str(file_path.relative_to(self.wiki_path)),
                "action": "created",
                "message": f"已创建实体: {entity_name}"
            }
    
    def update_index(self) -> Dict[str, Any]:
        """重新生成wiki索引"""
        stats = {
            "sessions": 0,
            "entities": 0,
            "concepts": 0,
            "projects": 0,
            "decisions": 0,
            "outputs": 0
        }
        
        recent_sessions = []
        
        # 统计各分类
        for category in stats.keys():
            category_path = self.wiki_path / category
            if category_path.exists():
                files = list(category_path.glob("*.md"))
                stats[category] = len([f for f in files if f.stem != 'index'])
                
                # 收集最近的session
                if category == "sessions" and files:
                    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    recent_sessions = [
                        {
                            "name": f.stem,
                            "date": datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d')
                        }
                        for f in files[:5]
                    ]
        
        # 生成新的index
        index_content = f"""# Personal Wiki Index

**最后更新**: {datetime.now().strftime('%Y-%m-%d')}
**版本**: v2.0 — 与digital life集成

## 统计
- 会话数: {stats['sessions']}
- 实体数: {stats['entities']}
- 概念数: {stats['concepts']}
- 项目数: {stats['projects']}

## 最近会话
"""
        for session in recent_sessions:
            index_content += f"- [[Session: {session['name']}]] — {session['date']}\n"
        
        index_content += """
## 分类

### 会话 (sessions)
与数字生命的对话记录和决策

### 实体 (entities)
人物、工具、概念等实体定义

### 项目 (projects)
正在进行的项目和任务

### 决策 (decisions)
重要决策和选择理由

### 产出 (outputs)
文章、代码、设计等产出物

## 标签

### 按领域
- AI工程化
- SRE
- 金融科技

### 按应用场景
- 待添加
"""
        
        self.index_path.write_text(index_content, encoding='utf-8')
        
        return {
            "success": True,
            "message": "已更新wiki索引",
            "stats": stats
        }
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """在wiki中搜索关键词"""
        results = []
        
        for md_file in self.wiki_path.rglob("*.md"):
            try:
                content = md_file.read_text(encoding='utf-8')
                if query.lower() in content.lower():
                    # 提取标题
                    title = md_file.stem
                    for line in content.split('\n'):
                        if line.startswith('# '):
                            title = line[2:].strip()
                            break
                    
                    results.append({
                        "file": str(md_file.relative_to(self.wiki_path)),
                        "title": title,
                        "category": md_file.parent.name
                    })
            except:
                continue
        
        return results[:10]  # 限制返回数量
