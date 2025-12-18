// personas.js - 简化版
document.addEventListener('DOMContentLoaded', function() {
    let personas = [];
    let expandedId = null;
    
    // 加载数据
    async function loadPersonas() {
        try {
            const response = await fetch('/api/personas');
            const data = await response.json();
            if (data.success) {
                personas = data.personas;
                renderPersonas();
            }
        } catch (error) {
            showMessage('加载失败', 'error');
        }
    }
    
    // 渲染卡片
    function renderPersonas() {
        const container = document.getElementById('personasList');
        if (!container) return;
        
        if (personas.length === 0) {
            container.innerHTML = `
                <div class="empty-personas">
                    <i class="fas fa-user-slash"></i>
                    <p>暂无人格数据</p>
                    <button onclick="addNewPersona()" class="btn btn-primary">
                        <i class="fas fa-plus"></i> 创建第一个
                    </button>
                </div>
            `;
            return;
        }
        
        let html = '';
        
        personas.forEach(persona => {
            const isExpanded = expandedId === persona.persona_id;
            const time = persona.polish_time || '未记录';
            const hasImage = persona.png_path && persona.png_path.trim() !== '';
            // 使用绝对路径
            const imageUrl = hasImage ? persona.png_path : getDefaultAvatar(persona.persona_id);
            
            html += `
                <div class="persona-card ${isExpanded ? 'expanded' : ''}">
                    <div class="persona-header" onclick="togglePersona('${persona.persona_id}')">
                        <div class="persona-info">
                            <div class="persona-avatar">
                                <img src="${imageUrl}" alt="${persona.persona_id}">
                            </div>
                            <div>
                                <h3>${persona.persona_id}</h3>
                                <p class="persona-time">${time}</p>
                            </div>
                        </div>
                        <div class="persona-actions">
                            <i class="fas fa-chevron-down expand-icon"></i>
                        </div>
                    </div>
                    
                    <div class="persona-content">
                        <div class="persona-main-content">
                            <div class="persona-image-section">
                                <div class="current-image">
                                    <img src="${imageUrl}" alt="${persona.persona_id}" class="persona-image">
                                    <div class="image-overlay">
                                        <span>${persona.png_path || '默认头像'}</span>
                                    </div>
                                </div>
                                <div class="image-controls">
                                    <input type="file" id="upload-${persona.persona_id}" 
                                           class="file-input" accept=".png,.jpg,.jpeg,.gif"
                                           style="display: none;">
                                    <div class="upload-buttons">
                                        <button class="btn btn-small" onclick="document.getElementById('upload-${persona.persona_id}').click()">
                                            <i class="fas fa-upload"></i> 上传图片
                                        </button>
                                        <input type="text" class="form-control image-path" 
                                               value="${escapeHtml(persona.png_path || '')}" 
                                               placeholder="/img/xxx.png"
                                               onchange="updateImagePath('${persona.persona_id}', this.value)">
                                    </div>
                                </div>
                            </div>
                            
                            <div class="persona-details">
                                <div class="detail-group">
                                    <label><i class="fas fa-id-card"></i> 人格ID</label>
                                    <input type="text" class="form-control" value="${escapeHtml(persona.persona_id)}" 
                                           onchange="updatePersonaId('${persona.persona_id}', this.value)">
                                </div>
                                
                                <div class="detail-group">
                                    <label><i class="fas fa-comment-dots"></i> 描述提示词</label>
                                    <textarea class="form-control textarea" rows="4"
                                              onchange="updatePrompt('${persona.persona_id}', this.value)">${escapeHtml(persona.polished_prompt || '')}</textarea>
                                </div>
                                
                                <div class="persona-footer">
                                    <button class="btn btn-primary" onclick="savePersona('${persona.persona_id}')">
                                        <i class="fas fa-save"></i> 保存
                                    </button>
                                    <button class="btn btn-danger" onclick="deletePersona('${persona.persona_id}')">
                                        <i class="fas fa-trash"></i> 删除
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
        // 设置上传事件
        personas.forEach(persona => {
            const input = document.getElementById(`upload-${persona.persona_id}`);
            if (input) {
                input.onchange = () => uploadImage(persona.persona_id, input);
            }
        });
    }
    
    // 默认头像
    function getDefaultAvatar(personaId) {
        const colors = ['9DCC9E', '6C8EBF', 'D2B48C', 'FFB6C1', '9370DB'];
        const index = personaId.split('').reduce((a, b) => a + b.charCodeAt(0), 0) % colors.length;
        return `https://ui-avatars.com/api/?name=${encodeURIComponent(personaId)}&background=${colors[index]}&color=fff&bold=true&size=150`;
    }
    
    // 全局函数
    window.togglePersona = function(personaId) {
        expandedId = expandedId === personaId ? null : personaId;
        renderPersonas();
    };
    
    window.updatePersonaId = function(oldId, newId) {
        const index = personas.findIndex(p => p.persona_id === oldId);
        if (index !== -1 && newId) {
            personas[index].persona_id = newId;
            expandedId = newId;
            personas[index].polish_time = new Date().toLocaleString('zh-CN');
            savePersonas(); // 修复：添加保存调用
        }
    };
    
    window.updateImagePath = function(personaId, path) {
        const index = personas.findIndex(p => p.persona_id === personaId);
        if (index !== -1) {
            const trimmedPath = path.trim();
            personas[index].png_path = trimmedPath;
            personas[index].polish_time = new Date().toLocaleString('zh-CN');
            savePersonas(); // 修复：添加保存调用
        }
    };
    
    window.updatePrompt = function(personaId, prompt) {
        const index = personas.findIndex(p => p.persona_id === personaId);
        if (index !== -1) {
            personas[index].polished_prompt = prompt;
            personas[index].polish_time = new Date().toLocaleString('zh-CN');
            savePersonas(); // 修复：添加保存调用
        }
    };
    
    // 上传图片
    async function uploadImage(personaId, input) {
        const file = input.files[0];
        if (!file) return;
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            showMessage('上传中...', 'info');
            
            const response = await fetch('/api/upload-image', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                const index = personas.findIndex(p => p.persona_id === personaId);
                if (index !== -1) {
                    personas[index].png_path = result.url; // 使用绝对路径
                    personas[index].polish_time = new Date().toLocaleString('zh-CN');
                    await savePersonas(); // 这里已经有保存调用
                    showMessage('上传成功', 'success');
                    renderPersonas();
                }
            } else {
                showMessage(result.message || '上传失败', 'error');
            }
        } catch (error) {
            showMessage('上传失败', 'error');
        }
        
        input.value = '';
    }
    
    // 保存人格
    window.savePersona = async function(personaId) {
        const index = personas.findIndex(p => p.persona_id === personaId);
        if (index !== -1) {
            await savePersonas();
            showMessage('保存成功', 'success');
        }
    };
    
    // 删除人格
    window.deletePersona = function(personaId) {
        if (confirm(`删除人格 "${personaId}"？`)) {
            const index = personas.findIndex(p => p.persona_id === personaId);
            if (index !== -1) {
                personas.splice(index, 1);
                savePersonas(); // 这里有保存调用
                expandedId = null;
                showMessage('删除成功', 'success');
            }
        }
    };
    
    // 添加人格
    window.addNewPersona = function() {
        const newId = `character_${Date.now()}`;
        personas.push({
            persona_id: newId,
            png_path: '',
            polished_prompt: '请输入人格描述...',
            polish_time: new Date().toLocaleString('zh-CN')
        });
        savePersonas(); // 这里有保存调用
        expandedId = newId;
        showMessage('创建成功', 'success');
    };
    
    // 保存数据
    async function savePersonas() {
        try {
            const response = await fetch('/api/personas', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(personas)
            });
            
            if (response.ok) {
                renderPersonas();
                return true;
            }
        } catch (error) {
            showMessage('保存失败', 'error');
        }
        return false;
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
    
    // 初始化
    loadPersonas();
    
    // 添加按钮事件
    document.getElementById('addPersonaBtn')?.addEventListener('click', addNewPersona);
});