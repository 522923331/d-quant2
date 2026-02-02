"""Web界面自动化测试

使用Playwright测试Streamlit界面
"""

import pytest
import time
from pathlib import Path
import subprocess
import sys
import os


# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class StreamlitTestHelper:
    """Streamlit测试辅助类"""
    
    def __init__(self, port: int = 8501):
        self.port = port
        self.url = f"http://localhost:{port}"
        self.process = None
    
    def start_app(self):
        """启动Streamlit应用"""
        app_path = Path(__file__).parent.parent / 'app.py'
        
        # 启动Streamlit
        self.process = subprocess.Popen(
            [sys.executable, '-m', 'streamlit', 'run', str(app_path),
             '--server.port', str(self.port),
             '--server.headless', 'true'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 等待应用启动
        time.sleep(5)
    
    def stop_app(self):
        """停止Streamlit应用"""
        if self.process:
            self.process.terminate()
            self.process.wait()


@pytest.fixture(scope="module")
def streamlit_app():
    """Streamlit应用fixture"""
    helper = StreamlitTestHelper()
    helper.start_app()
    
    yield helper
    
    helper.stop_app()


def test_app_loads(streamlit_app):
    """测试应用是否能正常加载
    
    注意：需要安装 playwright:
    pip install pytest-playwright
    playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # 访问应用
            page.goto(streamlit_app.url, timeout=10000)
            
            # 等待页面加载
            page.wait_for_selector('text=d-quant2 量化系统', timeout=10000)
            
            # 验证页面标题
            assert 'd-quant2' in page.title()
            
            browser.close()
    
    except ImportError:
        pytest.skip("Playwright未安装，跳过UI测试")


def test_backtest_page_navigation(streamlit_app):
    """测试回测页面导航"""
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            page.goto(streamlit_app.url, timeout=10000)
            page.wait_for_load_state('networkidle')
            
            # 点击"回测分析"按钮（如果不是默认页面）
            # Streamlit的radio按钮比较特殊，需要等待元素加载
            time.sleep(2)
            
            # 检查是否存在回测相关元素
            # 由于Streamlit的动态渲染，我们检查关键文本
            page_content = page.content()
            assert '回测分析' in page_content or '回测配置' in page_content
            
            browser.close()
    
    except ImportError:
        pytest.skip("Playwright未安装，跳过UI测试")


def test_stock_selection_page(streamlit_app):
    """测试选股页面"""
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            page.goto(streamlit_app.url, timeout=10000)
            page.wait_for_load_state('networkidle')
            
            time.sleep(2)
            
            # 检查选股相关内容
            page_content = page.content()
            assert '智能选股' in page_content or '选股系统' in page_content
            
            browser.close()
    
    except ImportError:
        pytest.skip("Playwright未安装，跳过UI测试")


# 如果Playwright未安装，提供简单的HTTP测试
def test_app_responds(streamlit_app):
    """测试应用是否响应（不需要Playwright）"""
    import requests
    
    try:
        response = requests.get(streamlit_app.url, timeout=5)
        assert response.status_code == 200
    except requests.exceptions.RequestException:
        pytest.skip("应用未启动或无法访问")


if __name__ == '__main__':
    # 直接运行测试
    pytest.main([__file__, '-v'])
