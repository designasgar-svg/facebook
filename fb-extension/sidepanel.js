let textTemplates = JSON.parse(localStorage.getItem('fb_text_templates')) || {
    "پیش‌فرض": "سلام دوستان، مدل‌های جدید منبت و CNC آماده شد..."
};

let selectedImages = [];

function showStatus(text, isError = false) {
    const status = document.getElementById('statusMessage');
    status.innerText = text;
    status.style.backgroundColor = isError ? '#dc3545' : '#28a745';
    status.style.display = 'block';
    
    setTimeout(() => {
        status.style.display = 'none';
    }, 2000);
}

function initTemplates() {
    const select = document.getElementById('textTemplateSelect');
    select.innerHTML = '<option value="">-- انتخاب قالب موجود --</option>';
    for (let name in textTemplates) {
        const opt = document.createElement('option');
        opt.value = name;
        opt.innerText = name;
        select.appendChild(opt);
    }
}

function onTemplateSelected() {
    const name = document.getElementById('textTemplateSelect').value;
    if (name && textTemplates[name]) {
        document.getElementById('adTextContent').value = textTemplates[name];
    } else {
        document.getElementById('adTextContent').value = '';
    }
}

function createNewTemplate() {
    const name = document.getElementById('newTemplateName').value.trim();
    if (!name) {
        showStatus('لطفاً نام قالب را وارد کنید.', true);
        return;
    }
    if (textTemplates[name]) {
        showStatus('این قالب از قبل وجود دارد.', true);
        return;
    }
    textTemplates[name] = "متن تبلیغاتی برای " + name + "...";
    localStorage.setItem('fb_text_templates', JSON.stringify(textTemplates));
    document.getElementById('newTemplateName').value = '';
    initTemplates();
    document.getElementById('textTemplateSelect').value = name;
    onTemplateSelected();
    showStatus(`قالب "${name}" ایجاد شد!`);
}

function saveCurrentText() {
    const name = document.getElementById('textTemplateSelect').value;
    if (!name) {
        showStatus('ابتدا یک قالب از منو انتخاب کنید.', true);
        return;
    }
    textTemplates[name] = document.getElementById('adTextContent').value;
    localStorage.setItem('fb_text_templates', JSON.stringify(textTemplates));
    showStatus('تغییرات ذخیره شد!');
}

// تابع جدید برای حذف قالب انتخاب شده
// تابع اصلاح‌شده و ایمن برای حذف قالب
function deleteCurrentTemplate() {
    const select = document.getElementById('textTemplateSelect');
    const name = select.value;

    // بررسی اینکه آیا قالبی انتخاب شده است یا خیر
    if (!name) {
        showStatus('ابتدا یک قالب را از منو انتخاب کنید.', true);
        return;
    }

    // جلوگیری از حذف آخرین قالب باقی‌مانده
    if (Object.keys(textTemplates).length <= 1) {
        showStatus('حداقل یک قالب باید در سیستم بماند.', true);
        return;
    }

    // حذف قالب از شیء و ذخیره در حافظه
    delete textTemplates[name];
    localStorage.setItem('fb_text_templates', JSON.stringify(textTemplates));

    // به‌روزرسانی منو و پاک کردن کادر متن
    initTemplates();
    document.getElementById('adTextContent').value = '';
    
    showStatus(`قالب "${name}" حذف شد.`);
}

function copyAdText() {
    const textarea = document.getElementById('adTextContent');
    textarea.select();
    document.execCommand('copy');
    showStatus('متن کپی شد! در فیسبوک Ctrl+V بزنید.');
}

function handleFolderSelected(event) {
    const files = event.target.files;
    const gallery = document.getElementById('imageGallery');
    gallery.innerHTML = '';
    selectedImages = [];

    const validExts = ['.png', '.jpg', '.jpeg', '.webp', '.gif'];
    let count = 0;

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const name = file.name.toLowerCase();
        
        if (validExts.some(ext => name.endsWith(ext))) {
            const objectUrl = URL.createObjectURL(file);
            const img = document.createElement('img');
            img.src = objectUrl;
            img.className = 'image-thumb';
            img.draggable = true;
            img.title = file.name;
            img.fileObj = file;

            img.addEventListener('click', () => {
                if (img.classList.contains('selected')) {
                    img.classList.remove('selected');
                    selectedImages = selectedImages.filter(el => el !== img);
                } else {
                    img.classList.add('selected');
                    selectedImages.push(img);
                }
            });

            gallery.appendChild(img);
            count++;
        }
    }

    if (count === 0) {
        gallery.innerHTML = '<p style="text-align:center; color:#777; grid-column: 1/-1; font-size: 11px;">تصویری در این پوشه یافت نشد.</p>';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initTemplates();

    document.getElementById('textTemplateSelect').addEventListener('change', onTemplateSelected);
    document.getElementById('createNewTemplateBtn').addEventListener('click', createNewTemplate);
    document.getElementById('saveTextBtn').addEventListener('click', saveCurrentText);
    document.getElementById('deleteTemplateBtn').addEventListener('click', deleteCurrentTemplate);
    document.getElementById('copyTextBtn').addEventListener('click', copyAdText);

    const folderInput = document.getElementById('folderInput');
    document.getElementById('selectFolderBtn').addEventListener('click', () => {
        folderInput.click();
    });
    folderInput.addEventListener('change', handleFolderSelected);
});