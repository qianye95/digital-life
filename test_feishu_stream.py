"""飞书流式输出功能的 pytest 测试用例。"""

import pytest
from interfaces.ingress.feishu_stream import FeishuStreamSender
from interfaces.ingress.feishu_streaming_adapter import FeishuStreamingAdapter


class TestFeishuStreamSender:
    """测试 FeishuStreamSender 类。"""

    def test_initialization(self):
        """测试初始化参数。"""
        sender = FeishuStreamSender(
            domain='https://open.feishu.cn',
            app_id='test_app',
            app_secret='test_secret',
            update_interval=0.5
        )
        assert sender._domain == 'https://open.feishu.cn'
        assert sender._app_id == 'test_app'
        assert sender._app_secret == 'test_secret'
        assert sender._update_interval == 0.5
        assert sender._message_id is None
        assert sender._is_streaming is False

    def test_default_update_interval(self):
        """测试默认更新间隔。"""
        sender = FeishuStreamSender(
            domain='https://open.feishu.cn',
            app_id='test_app',
            app_secret='test_secret'
        )
        assert sender._update_interval == 0.3


class TestFeishuStreamingAdapter:
    """测试 FeishuStreamingAdapter 类。"""

    def test_initialization_streaming_enabled(self):
        """测试启用流式模式初始化。"""
        adapter = FeishuStreamingAdapter(
            app_id='test_app',
            app_secret='test_secret',
            enable_streaming=True
        )
        assert adapter.enable_streaming is True
        assert adapter._active_stream is None

    def test_initialization_streaming_disabled(self):
        """测试禁用流式模式初始化。"""
        adapter = FeishuStreamingAdapter(
            app_id='test_app',
            app_secret='test_secret',
            enable_streaming=False
        )
        assert adapter.enable_streaming is False

    def test_default_streaming_disabled(self):
        """测试默认禁用流式模式。"""
        adapter = FeishuStreamingAdapter(
            app_id='test_app',
            app_secret='test_secret'
        )
        assert adapter.enable_streaming is False

    def test_streaming_methods_exist(self):
        """测试流式方法存在。"""
        adapter = FeishuStreamingAdapter(
            app_id='test_app',
            app_secret='test_secret',
            enable_streaming=True
        )
        assert hasattr(adapter, 'send_streaming')
        assert hasattr(adapter, 'send_chunks')
        assert hasattr(adapter, 'send_generator')
        assert callable(adapter.send_streaming)
        assert callable(adapter.send_chunks)
        assert callable(adapter.send_generator)

    def test_inherits_from_feishu_adapter(self):
        """测试继承关系。"""
        from interfaces.ingress.feishu import FeishuAdapter
        adapter = FeishuStreamingAdapter(
            app_id='test_app',
            app_secret='test_secret'
        )
        assert isinstance(adapter, FeishuAdapter)

    def test_original_send_method_preserved(self):
        """测试原始 send 方法保留。"""
        adapter = FeishuStreamingAdapter(
            app_id='test_app',
            app_secret='test_secret'
        )
        assert hasattr(adapter, 'send')
        assert callable(adapter.send)


class TestStreamingModeSwitching:
    """测试流式/非流式模式切换。"""

    def test_enable_streaming_property(self):
        """测试 enable_streaming 属性可修改。"""
        adapter = FeishuStreamingAdapter(
            app_id='test_app',
            app_secret='test_secret',
            enable_streaming=False
        )
        assert adapter.enable_streaming is False
        
        adapter.enable_streaming = True
        assert adapter.enable_streaming is True
        
        adapter.enable_streaming = False
        assert adapter.enable_streaming is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
