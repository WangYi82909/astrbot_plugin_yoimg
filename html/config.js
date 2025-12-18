// config.js - 修复保存问题
document.addEventListener('DOMContentLoaded', function() {
    let CONFIG_SCHEMA = {};
    let currentConfig = {};
    
    // 加载配置
    async function loadConfig() {
        try {
            const response = await fetch('/api/config');
            const data = await response.json();
            
            if (data.success) {
                CONFIG_SCHEMA = data.schema;
                currentConfig = data.config;
                console.log('配置加载成功，字段数:', Object.keys(CONFIG_SCHEMA).length);
                renderForm();
            } else {
                showMessage('加载配置失败', 'error');
            }
        } catch (error) {
            console.error('加载配置失败:', error);
            showMessage('连接服务器失败', 'error');
        }
    }
    
    // 渲染表单
    function renderForm() {
        const form = document.getElementById('configForm');
        if (!form) return;
        
        if (Object.keys(CONFIG_SCHEMA).length === 0) {
            form.innerHTML = '<div style="padding: 20px; text-align: center;">没有配置项</div>';
            return;
        }
        
        let html = '';
        
        for (const [key, schema] of Object.entries(CONFIG_SCHEMA)) {
            const value = currentConfig[key] || schema.default || '';
            html += renderField(key, schema, value);
        }
        
        form.innerHTML = html;
    }
    
    function renderField(key, schema, value) {
        let input = '';
        const desc = schema.description || key;
        
        switch(schema.type) {
            case 'string':
            case 'text':
                input = `<input type="text" id="${key}" class="form-control" value="${escapeHtml(value)}">`;
                break;
            case 'int':
            case 'float':
                input = `<input type="number" id="${key}" class="form-control" value="${value}">`;
                break;
            case 'bool':
                const checked = value ? 'checked' : '';
                input = `
                    <div class="switch-group">
                        <label class="switch">
                            <input type="checkbox" id="${key}" ${checked}>
                            <span class="switch-slider"></span>
                        </label>
                    </div>
                `;
                break;
            case 'list':
                // 列表类型简化为文本框，用逗号分隔
                const listValue = Array.isArray(value) ? value.join(', ') : value;
                input = `<input type="text" id="${key}" class="form-control" value="${escapeHtml(listValue)}">`;
                break;
            default:
                input = `<input type="text" id="${key}" class="form-control" value="${escapeHtml(value)}">`;
        }
        
        return `
            <div class="form-group">
                <label>${desc}</label>
                ${input}
            </div>
        `;
    }
    
    // 收集表单数据
    function collectFormData() {
        const formData = {};
        
        for (const [key, schema] of Object.entries(CONFIG_SCHEMA)) {
            const element = document.getElementById(key);
            if (element) {
                switch(schema.type) {
                    case 'bool':
                        formData[key] = element.checked;
                        break;
                    case 'list':
                        // 将逗号分隔的字符串转为数组
                        const str = element.value.trim();
                        formData[key] = str ? str.split(',').map(s => s.trim()) : [];
                        break;
                    case 'int':
                        formData[key] = parseInt(element.value) || schema.default || 0;
                        break;
                    case 'float':
                        formData[key] = parseFloat(element.value) || schema.default || 0.0;
                        break;
                    default:
                        formData[key] = element.value.trim();
                }
            }
        }
        
        return formData;
    }
    
    // 保存配置
    async function saveConfig(configData) {
        try {
            console.log('发送配置数据:', configData);
            
            const response = await fetch('/api/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(configData)
            });
            
            const result = await response.json();
            console.log('保存结果:', result);
            return result;
        } catch (error) {
            console.error('保存配置失败:', error);
            return {success: false, message: error.message};
        }
    }
    
    // 显示消息
    function showMessage(message, type = 'success') {
        const oldMsg = document.querySelector('.floating-message');
        if (oldMsg) oldMsg.remove();
        
        const msgDiv = document.createElement('div');
        msgDiv.className = `floating-message ${type}`;
        msgDiv.innerHTML = `<i class="fas fa-${type === 'success' ? 'check' : 'times'}"></i> ${message}`;
        
        document.body.appendChild(msgDiv);
        
        setTimeout(() => msgDiv.classList.add('show'), 10);
        setTimeout(() => {
            msgDiv.classList.remove('show');
            setTimeout(() => msgDiv.remove(), 300);
        }, 3000);
    }
    
    function escapeHtml(text) {
        return String(text || '').replace(/[&<>"']/g, m => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;',
            '"': '&quot;', "'": '&#39;'
        }[m]));
    }
    
    // 事件监听
    document.getElementById('configForm')?.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = collectFormData();
        console.log('表单数据:', formData);
        
        const result = await saveConfig(formData);
        if (result.success) {
            showMessage('配置保存成功', 'success');
            currentConfig = formData;
        } else {
            showMessage(`保存失败: ${result.message}`, 'error');
        }
    });
    
    // 重置按钮
    document.getElementById('resetBtn')?.addEventListener('click', async function() {
        if (confirm('重置为默认值？')) {
            // 重新加载配置
            await loadConfig();
            showMessage('已重置', 'success');
        }
    });
    
    // 返回按钮
    document.getElementById('backBtn')?.addEventListener('click', function() {
        window.location.href = '/';
    });
    
    // 初始化
    loadConfig();
});