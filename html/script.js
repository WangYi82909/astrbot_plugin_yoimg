// DOM加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 获取DOM元素
    const menuToggle = document.getElementById('menuToggle');
    const closeSidebar = document.getElementById('closeSidebar');
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.querySelector('.main-content');
    const navItems = document.querySelectorAll('.sidebar-nav li');
    const totalCallsElement = document.getElementById('totalCalls');
    const todayCallsElement = document.getElementById('todayCalls');
    
    // 模拟数据
    const totalCalls = 999;
    const todayCalls = 999;
    
    // 打开侧边栏
    menuToggle.addEventListener('click', function() {
        sidebar.classList.add('active');
        mainContent.classList.add('sidebar-open');
    });
    
    // 关闭侧边栏
    closeSidebar.addEventListener('click', function() {
        sidebar.classList.remove('active');
        mainContent.classList.remove('sidebar-open');
    });
    
    // 修复：侧边栏导航点击事件
    navItems.forEach(item => {
        const link = item.querySelector('a');
        if (!link) return;
        
        link.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            
            // 处理特殊链接
            if (!href || href === '#' || href.startsWith('javascript:')) {
                e.preventDefault();
                return;
            }
            
            // 如果不是当前页面才处理
            if (href !== window.location.pathname.split('/').pop()) {
                // 移除所有active类
                navItems.forEach(navItem => {
                    navItem.classList.remove('active');
                });
                
                // 为当前点击项添加active类
                item.classList.add('active');
                
                // 移动端点击后自动关闭侧边栏
                if (window.innerWidth <= 768) {
                    sidebar.classList.remove('active');
                    mainContent.classList.remove('sidebar-open');
                }
                
                // 让浏览器处理页面跳转
                // 不要阻止默认行为，让链接正常工作
            }
        });
    });
    
    // 数字动画效果
    function animateNumber(element, targetNumber, duration = 1500) {
        const startNumber = 0;
        const increment = targetNumber / (duration / 16);
        let currentNumber = startNumber;
        
        const timer = setInterval(() => {
            currentNumber += increment;
            if (currentNumber >= targetNumber) {
                currentNumber = targetNumber;
                clearInterval(timer);
            }
            element.textContent = Math.floor(currentNumber).toLocaleString();
        }, 16);
    }
    
    // 初始化数字动画
    setTimeout(() => {
        animateNumber(totalCallsElement, totalCalls);
        animateNumber(todayCallsElement, todayCalls);
    }, 300);
});