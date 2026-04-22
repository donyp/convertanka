/**
 * Custom Toast Notification System
 */
const Toast = {
    init() {
        if (!document.getElementById('toast-container')) {
            const container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }
    },
    show(message, type = 'info', duration = 3000) {
        this.init();
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };

        toast.innerHTML = `
            <div class="toast-icon"><i class="fas ${icons[type] || icons.info}"></i></div>
            <div class="toast-content">${message}</div>
        `;

        container.appendChild(toast);

        // Force reflow for animation
        setTimeout(() => toast.classList.add('show'), 10);

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 400);
        }, duration);
    }
};

document.addEventListener('DOMContentLoaded', () => {
    Toast.init();

    // Auth-related Elements
    const authModal = document.getElementById('auth-modal');
    const authForm = document.getElementById('auth-form');
    const openAuthBtn = document.getElementById('open-auth-btn');
    const closeAuthBtn = document.querySelector('.close-modal');
    const authSwitchLink = document.getElementById('auth-switch-link');
    const authTitle = document.getElementById('auth-title');
    const authSubmitBtn = document.getElementById('auth-submit-btn');
    const authEmail = document.getElementById('auth-email');
    const authPassword = document.getElementById('auth-password');
    const switchText = document.getElementById('switch-text');
    const authSwitchContainer = document.getElementById('auth-switch-container');

    // Forgot Password Elements
    const forgotEmailForm = document.getElementById('forgot-email-form');
    const forgotOtpForm = document.getElementById('forgot-otp-form');
    const resetPasswordForm = document.getElementById('reset-password-form');
    const openForgotPasswordBtn = document.getElementById('open-forgot-password');
    const backToLoginBtns = document.querySelectorAll('.action-back-login');
    const forgotEmailInput = document.getElementById('forgot-email-input');
    const forgotOtpInput = document.getElementById('forgot-otp-input');
    const sentOtpEmailDisplay = document.getElementById('sent-otp-email-display');
    const resetPasswordInput = document.getElementById('reset-password-input');
    const resetPasswordConfirm = document.getElementById('reset-password-confirm');

    // View Elements
    const loggedOutView = document.getElementById('logged-out-view');
    const loggedInView = document.getElementById('logged-in-view');
    const userEmailDisplay = document.getElementById('user-email');
    const userCodeDisplay = document.getElementById('user-code');
    const coinBalanceDisplay = document.getElementById('coin-balance');
    const adminLink = document.getElementById('admin-link');
    const logoutBtn = document.getElementById('logout-btn');

    // Main App Elements
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const convertBtn = document.getElementById('convert-btn');
    const fileInfo = document.getElementById('file-info');
    const uploadText = document.querySelector('.upload-text');
    const uploadIcon = document.querySelector('.upload-icon');
    const filenameDisplay = document.getElementById('filename-display');
    const removeFileBtn = document.getElementById('remove-file');
    const errorBox = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    const warningBox = document.getElementById('warning-message');
    const warningText = document.getElementById('warning-text');
    const successArea = document.getElementById('success-area');
    const downloadLink = document.getElementById('download-link');
    const progressContainer = document.getElementById('progress-container');
    const progressFill = document.getElementById('progress-fill');
    const progressStatus = document.getElementById('progress-status');
    const resetBtn = document.getElementById('reset-btn');

    let selectedFile = null;
    let selectedBank = 'bca';
    let isRegisterMode = false;
    let authToken = localStorage.getItem('auth_token');

    // --- State Management ---

    checkAuthState();

    async function checkAuthState() {
        if (!authToken) {
            showLoggedOut();
            return;
        }

        try {
            const res = await fetchWithAuth('/api/auth/me');
            if (!res.ok) throw new Error('Token expired');
            const user = await res.json();
            showLoggedIn(user);
        } catch (err) {
            console.warn('Session invalid:', err);
            logout();
        }
    }

    function showLoggedIn(user) {
        loggedOutView.classList.add('hidden');
        loggedInView.classList.remove('hidden');
        userEmailDisplay.textContent = user.full_name || user.email;
        userCodeDisplay.textContent = `CODE: ${user.unique_code}`;
        coinBalanceDisplay.textContent = user.coins;

        if (user.is_admin) adminLink.classList.remove('hidden');
        else adminLink.classList.add('hidden');

        // Enable upload area for users
        if (dropZone) dropZone.classList.remove('disabled');

        checkReady();
        if (selectedFile) analyzeFile(selectedFile);
    }

    function showLoggedOut() {
        if (loggedOutView) loggedOutView.classList.remove('hidden');
        if (loggedInView) loggedInView.classList.add('hidden');
        if (coinBalanceDisplay) coinBalanceDisplay.textContent = '...';
        if (adminLink) adminLink.classList.add('hidden');

        // Disable upload area for guests
        if (dropZone) dropZone.classList.add('disabled');

        checkReady();
    }

    function logout() {
        localStorage.removeItem('auth_token');
        authToken = null;
        showLoggedOut();
        resetApp();
    }

    // --- API Helper ---

    async function fetchWithAuth(url, options = {}) {
        const headers = options.headers || {};
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }
        return fetch(url, { ...options, headers });
    }

    // --- Auth Event Listeners ---

    if (openAuthBtn) openAuthBtn.onclick = () => {
        isRegisterMode = false;
        updateAuthUI();
        authModal.classList.remove('hidden');
    };

    if (closeAuthBtn) closeAuthBtn.onclick = () => authModal.classList.add('hidden');

    if (authSwitchLink) authSwitchLink.onclick = (e) => {
        e.preventDefault();
        isRegisterMode = !isRegisterMode;
        updateAuthUI();
    };

    function updateAuthUI() {
        // Reset sub-views in auth modal
        authForm.classList.remove('hidden');
        forgotEmailForm.classList.add('hidden');
        forgotOtpForm.classList.add('hidden');
        resetPasswordForm.classList.add('hidden');
        authSwitchContainer.classList.remove('hidden');

        if (isRegisterMode) {
            authTitle.textContent = "Daftar Akun Baru";
            authSubmitBtn.textContent = "Daftar Sekarang";
            switchText.textContent = "Sudah punya akun?";
            authSwitchLink.textContent = "Login Sini";
        } else {
            authTitle.textContent = "Login Ke Akun";
            authSubmitBtn.textContent = "Login";
            switchText.textContent = "Belum punya akun?";
            authSwitchLink.textContent = "Daftar Sekarang";
        }
    }

    if (authForm) authForm.onsubmit = async (e) => {
        e.preventDefault();
        const email = authEmail.value;
        const password = authPassword.value;

        const endpoint = isRegisterMode ? '/api/auth/register' : '/api/auth/login';
        const formData = new FormData();

        if (isRegisterMode) {
            formData.append('email', email);
            formData.append('password', password);
        } else {
            formData.append('username', email);
            formData.append('password', password);
        }

        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (res.ok) {
                if (isRegisterMode) {
                    Toast.show('Registrasi berhasil! Silakan login.', 'success');
                    isRegisterMode = false;
                    updateAuthUI();
                } else {
                    authToken = data.access_token;
                    localStorage.setItem('auth_token', authToken);
                    authModal.classList.add('hidden');
                    checkAuthState();
                }
            } else {
                Toast.show(data.detail || 'Gagal masuk.', 'error');
            }
        } catch (err) {
            Toast.show('Terjadi kesalahan koneksi.', 'error');
        }
    };

    // --- Forgot Password Flow ---
    let currentResetEmail = '';
    let currentResetOtp = '';

    if (openForgotPasswordBtn) openForgotPasswordBtn.onclick = (e) => {
        e.preventDefault();
        authTitle.textContent = "Lupa Password";
        authForm.classList.add('hidden');
        authSwitchContainer.classList.add('hidden');
        forgotEmailForm.classList.remove('hidden');
    };

    backToLoginBtns.forEach(btn => btn.onclick = () => {
        isRegisterMode = false;
        updateAuthUI();
    });

    if (forgotEmailForm) forgotEmailForm.onsubmit = async (e) => {
        e.preventDefault();
        const email = forgotEmailInput.value;
        const btn = document.getElementById('btn-forgot-email');
        btn.disabled = true;
        btn.textContent = 'Mengirim...';

        try {
            const formData = new FormData();
            formData.append('email', email);

            const res = await fetch('/api/auth/forgot-password', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();

            if (res.ok) {
                Toast.show(data.message, 'success');
                currentResetEmail = email;
                sentOtpEmailDisplay.textContent = email;
                forgotEmailForm.classList.add('hidden');
                forgotOtpForm.classList.remove('hidden');
            } else {
                Toast.show(data.detail || 'Gagal mengirim OTP.', 'error');
            }
        } catch (err) {
            Toast.show('Terjadi kesalahan koneksi.', 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Kirim OTP';
        }
    };

    if (forgotOtpForm) forgotOtpForm.onsubmit = async (e) => {
        e.preventDefault();
        const otp = forgotOtpInput.value;
        const btn = document.getElementById('btn-forgot-otp');
        btn.disabled = true;
        btn.textContent = 'Memverifikasi...';

        try {
            const formData = new FormData();
            formData.append('email', currentResetEmail);
            formData.append('otp', otp);

            const res = await fetch('/api/auth/verify-otp', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();

            if (res.ok) {
                Toast.show(data.message, 'success');
                currentResetOtp = otp;
                forgotOtpForm.classList.add('hidden');
                resetPasswordForm.classList.remove('hidden');
            } else {
                Toast.show(data.detail || 'OTP salah atau kedaluwarsa.', 'error');
            }
        } catch (err) {
            Toast.show('Terjadi kesalahan koneksi.', 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Verifikasi OTP';
        }
    };

    if (resetPasswordForm) resetPasswordForm.onsubmit = async (e) => {
        e.preventDefault();
        const newPassword = resetPasswordInput.value;
        const confirmPassword = resetPasswordConfirm.value;

        if (newPassword !== confirmPassword) {
            Toast.show("Konfirmasi password tidak cocok.", "error");
            return;
        }

        const btn = document.getElementById('btn-reset-password');
        btn.disabled = true;
        btn.textContent = 'Menyimpan...';

        try {
            const formData = new FormData();
            formData.append('email', currentResetEmail);
            formData.append('otp', currentResetOtp);
            formData.append('new_password', newPassword);

            const res = await fetch('/api/auth/reset-password', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();

            if (res.ok) {
                Toast.show(data.message, 'success');
                isRegisterMode = false;
                updateAuthUI();
                // Auto fill email to login form for convenience
                if (authEmail) authEmail.value = currentResetEmail;
                if (authPassword) authPassword.value = '';
            } else {
                Toast.show(data.detail || 'Gagal mengubah password.', 'error');
            }
        } catch (err) {
            Toast.show('Terjadi kesalahan koneksi.', 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Simpan Password Baru';
        }
    };

    if (logoutBtn) logoutBtn.onclick = logout;

    // --- Bank Dropdown logic ---
    const dropdown = document.getElementById('bank-dropdown');
    if (dropdown) {
        const selectSelected = dropdown.querySelector('.select-selected');
        const selectItems = dropdown.querySelector('.select-items');
        const selectOptions = dropdown.querySelectorAll('.select-option');
        const currentLogo = document.getElementById('selected-bank-logo');
        const currentText = document.getElementById('selected-bank-text');

        selectSelected.onclick = (e) => {
            e.stopPropagation();
            dropdown.classList.toggle('active');
            selectItems.classList.toggle('select-hide');
        };

        selectOptions.forEach(opt => {
            opt.onclick = () => {
                selectedBank = opt.getAttribute('data-bank');
                currentLogo.className = opt.querySelector('i').className;
                currentText.textContent = opt.querySelector('span').textContent;
                dropdown.classList.remove('active');
                selectItems.classList.add('select-hide');
                resetSuccess();
                if (selectedFile) analyzeFile(selectedFile);
            };
        });

        document.addEventListener('click', () => {
            dropdown.classList.remove('active');
            selectItems.classList.add('select-hide');
        });
    }

    // --- File Upload Handlers ---
    if (dropZone) dropZone.onclick = () => fileInput.click();
    if (fileInput) fileInput.onchange = (e) => handleFiles(e.target.files);
    if (dropZone) {
        dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); };
        dropZone.ondragleave = () => dropZone.classList.remove('drag-over');
        dropZone.ondrop = (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            handleFiles(e.dataTransfer.files);
        };
    }

    async function handleFiles(files) {
        if (files.length > 1) { showError('Hanya 1 file diperbolehkan.'); return; }
        if (files.length > 0) {
            const file = files[0];
            if (file.type !== 'application/pdf') { showError('Hanya file PDF.'); return; }
            if (file.size > 10 * 1024 * 1024) { showError('Maksimal 10MB.'); return; }

            selectedFile = file;
            displayFile();
            hideError();
            hideWarning();
            resetSuccess();
            checkReady();
            analyzeFile(file);
        }
    }

    async function analyzeFile(file) {
        if (!authToken) {
            showWarning("Silakan login terlebih dahulu untuk menganalisa file.");
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('bank', selectedBank);

        const analysisLoader = document.getElementById('analysis-loader');
        const analysisFill = document.getElementById('analysis-fill');
        const coinCostDisplay = document.getElementById('coin-cost');
        const pageCountDisplay = document.getElementById('page-count');

        // Show loader, hide file info temporarily
        fileInfo.classList.add('hidden');
        analysisLoader.classList.remove('hidden');
        analysisFill.style.width = '0%';
        hideWarning();

        // Simulation for UI snappiness
        let progress = 0;
        const interval = setInterval(() => {
            if (progress < 90) {
                progress += 5;
                analysisFill.style.width = progress + '%';
            }
        }, 100);

        try {
            const response = await fetchWithAuth('/api/analyze-pdf', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            clearInterval(interval);
            analysisFill.style.width = '100%';

            setTimeout(() => {
                analysisLoader.classList.add('hidden');
                fileInfo.classList.remove('hidden');

                if (response.ok) {
                    pageCountDisplay.textContent = data.page_count;
                    coinCostDisplay.textContent = data.coin_cost;
                    if (data.mismatch_warning) showWarning(data.mismatch_warning);
                } else {
                    showError(data.detail || 'Gagal menganalisa file.');
                }
                checkReady();
            }, 400);
        } catch (err) {
            clearInterval(interval);
            analysisLoader.classList.add('hidden');
            showError('Error saat menganalisa file.');
        }
    }

    function displayFile() {
        filenameDisplay.textContent = selectedFile.name;
        fileInfo.classList.remove('hidden');
        uploadText.classList.add('hidden');
        uploadIcon.classList.add('hidden');
    }

    if (removeFileBtn) removeFileBtn.onclick = (e) => { e.stopPropagation(); clearFile(); };

    function clearFile() {
        selectedFile = null;
        fileInput.value = '';
        fileInfo.classList.add('hidden');
        uploadText.classList.remove('hidden');
        uploadIcon.classList.remove('hidden');
        checkReady();
        resetSuccess();
        hideWarning();
    }

    function checkReady() {
        if (convertBtn) convertBtn.disabled = !selectedFile || !authToken;
    }

    // --- Progress Simulation ---
    let progressInterval;
    function startProgress() {
        progressContainer.classList.remove('hidden');
        convertBtn.classList.add('hidden');
        hideWarning();
        let progress = 0;
        const steps = [
            { t: 30, txt: 'Menganalisa dokumen...' },
            { t: 60, txt: 'Memproses data...' },
            { t: 90, txt: 'Menyusun laporan...' },
            { t: 99, txt: 'Hampir selesai...' }
        ];
        let stepIdx = 0;
        progressFill.style.width = '0%';
        progressStatus.textContent = steps[0].txt;

        progressInterval = setInterval(() => {
            if (progress < 99) {
                progress += Math.random() * 5;
                if (progress > 99) progress = 99;
                progressFill.style.width = `${progress}%`;
                if (stepIdx < steps.length - 1 && progress > steps[stepIdx].t) {
                    stepIdx++;
                    progressStatus.textContent = steps[stepIdx].txt;
                }
            }
        }, 200);
    }

    // --- Conversion Logic ---
    if (convertBtn) convertBtn.onclick = async () => {
        if (!selectedFile || !authToken) return;

        hideError();
        resetSuccess();
        startProgress();

        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('bank', selectedBank);

        try {
            const response = await fetchWithAuth('/api/convert', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Konversi gagal.');
            }

            const newBalance = response.headers.get('X-New-Balance');
            if (newBalance) coinBalanceDisplay.textContent = newBalance;

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            downloadLink.href = url;
            downloadLink.download = `mutasi_${selectedBank}_${Date.now()}.xlsx`;

            clearInterval(progressInterval);
            progressFill.style.width = '100%';
            progressStatus.textContent = 'Selesai!';
            setTimeout(() => {
                progressContainer.classList.add('hidden');
                showSuccess();
            }, 600);
        } catch (err) {
            clearInterval(progressInterval);
            progressContainer.classList.add('hidden');
            convertBtn.classList.remove('hidden');
            showError(err.message);
        }
    };

    if (resetBtn) resetBtn.onclick = resetApp;

    function resetApp() {
        clearFile();
        resetSuccess();
        hideError();
        hideWarning();
        if (convertBtn) convertBtn.classList.remove('hidden');
        document.querySelector('.bank-selector').classList.remove('hidden');
        document.querySelector('.upload-area').classList.remove('hidden');
        progressFill.style.width = '0%';
        checkReady();
    }

    function showError(msg) { errorText.textContent = msg; errorBox.classList.remove('hidden'); successArea.classList.add('hidden'); }
    function hideError() { errorBox.classList.add('hidden'); }
    function showWarning(msg) { warningText.textContent = msg; warningBox.classList.remove('hidden'); }
    function hideWarning() { warningBox.classList.add('hidden'); }
    function showSuccess() {
        successArea.classList.remove('hidden');
        document.querySelector('.bank-selector').classList.add('hidden');
        document.querySelector('.upload-area').classList.add('hidden');
        successArea.scrollIntoView({ behavior: 'smooth' });
    }
    function resetSuccess() { successArea.classList.add('hidden'); }
});
