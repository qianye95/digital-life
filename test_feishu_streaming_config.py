"""测试飞书流式输出配置功能。"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from application.console.config_center import FIELDS


def test_streaming_config_field_exists():
    """测试流式输出配置字段存在。"""
    streaming_field = next(
        (f for f in FIELDS if f.key == "channels.feishu.enable_streaming"),
        None
    )
    assert streaming_field is not None, "流式输出配置字段不存在"
    assert streaming_field.label == "飞书流式输出"
    assert streaming_field.value_type == "boolean"
    assert streaming_field.default is False
    print("✓ 流式输出配置字段验证通过")


def test_streaming_config_field_properties():
    """测试流式输出配置字段属性。"""
    streaming_field = next(
        (f for f in FIELDS if f.key == "channels.feishu.enable_streaming"),
        None
    )
    assert streaming_field is not None
    
    # 验证字段属性
    assert streaming_field.path == "channels.feishu.enable_streaming"
    assert streaming_field.source == "yaml"
    assert streaming_field.section == "feishu"
    assert streaming_field.secret is False
    assert streaming_field.restart_required is True
    assert streaming_field.readonly is False
    
    # 验证描述
    assert "逐字显示" in streaming_field.description
    assert "打字机效果" in streaming_field.description
    
    print("✓ 流式输出配置字段属性验证通过")


def test_config_fields_count():
    """测试配置字段总数（包含新增的流式输出字段）。"""
    # 原 30 个字段 + 1 个流式输出字段 = 31 个
    assert len(FIELDS) == 31, f"配置字段总数应为 31，实际为 {len(FIELDS)}"
    print(f"✓ 配置字段总数验证通过：{len(FIELDS)} 个字段")


if __name__ == "__main__":
    print("开始测试飞书流式输出配置功能...")
    print()
    
    test_streaming_config_field_exists()
    test_streaming_config_field_properties()
    test_config_fields_count()
    
    print()
    print("所有测试通过 ✓")
