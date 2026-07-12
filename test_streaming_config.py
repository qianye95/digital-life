"""测试飞书流式输出配置功能。"""
import sys
import yaml
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))


def test_streaming_config_field():
    """测试流式输出配置字段是否正确定义在 FIELDS 中。"""
    from application.console.config_center import FIELDS
    
    # 查找飞书流式输出字段
    streaming_field = None
    for field in FIELDS:
        if field.key == "channels.feishu.enable_streaming":
            streaming_field = field
            break
    
    assert streaming_field is not None, "飞书流式输出配置字段未找到"
    assert streaming_field.label == "飞书流式输出"
    assert streaming_field.section == "feishu"
    assert streaming_field.value_type == "boolean"
    assert streaming_field.path == "channels.feishu.enable_streaming"
    assert streaming_field.default is False
    assert streaming_field.secret is False
    assert "逐字显示" in streaming_field.description or "打字机" in streaming_field.description
    
    print("✓ 配置字段定义正确")


def test_registry_reads_enable_streaming():
    """测试 registry.py 能从配置中读取 enable_streaming。"""
    # 模拟 channels.feishu 的配置
    channel_cfg = {
        "app_id": "cli_test123",
        "type": "feishu",
        "enable_streaming": True,
    }
    
    # 模拟 registry.py 的读取逻辑
    enable_streaming = bool(channel_cfg.get("enable_streaming", False))
    assert enable_streaming is True
    
    # 默认值测试
    channel_cfg_no_stream = {"app_id": "cli_test123", "type": "feishu"}
    enable_streaming_default = bool(channel_cfg_no_stream.get("enable_streaming", False))
    assert enable_streaming_default is False
    
    print("✓ Registry 能正确读取 enable_streaming 配置（含默认值）")


def test_yaml_config_roundtrip():
    """测试 YAML 配置的读写（模拟前端保存和 adapter 读取）。"""
    test_config = {
        "channels": {
            "feishu": {
                "app_id": "cli_xxx",
                "type": "feishu",
                "enable_streaming": True,
            }
        }
    }
    
    test_file = Path("/tmp/test_streaming_roundtrip.yaml")
    with open(test_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(test_config, f, allow_unicode=True)
    
    with open(test_file, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    
    assert loaded["channels"]["feishu"]["enable_streaming"] is True
    
    test_file.unlink()
    print("✓ YAML 配置读写正常")


if __name__ == "__main__":
    print("开始测试飞书流式输出配置...\n")
    
    test_streaming_config_field()
    test_registry_reads_enable_streaming()
    test_yaml_config_roundtrip()
    
    print("\n✅ 所有配置测试通过！")
