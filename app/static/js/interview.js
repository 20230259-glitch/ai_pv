(() => {
    'use strict';

    const job = window.INTERVIEW;
    const $ = (id) => document.getElementById(id);

    const transcript = $('transcript');
    const recordBtn = $('record');
    const analyzeBtn = $('analyze');
    const nextBtn = $('next');
    const questionEl = $('question');
    const qIndex = $('q-index');
    const timerEl = $('timer');
    const recordState = $('record-state');
    const speechState = $('speech-state');
    const result = $('result');
    const score = $('score');
    const criteriaResult = $('criteria-result');
    const feedback = $('feedback');
    const progress = $('session-progress');

    if (!job || !Array.isArray(job.questions) || job.questions.length === 0) {
        if (questionEl) {
            questionEl.textContent = 'Không tìm thấy câu hỏi phỏng vấn.';
        }

        if (analyzeBtn) analyzeBtn.disabled = true;
        if (recordBtn) recordBtn.disabled = true;

        return;
    }

    if (
        !transcript ||
        !recordBtn ||
        !analyzeBtn ||
        !nextBtn ||
        !questionEl ||
        !qIndex ||
        !timerEl ||
        !recordState ||
        !speechState ||
        !result ||
        !score ||
        !criteriaResult ||
        !feedback ||
        !progress
    ) {
        console.error('Không tìm thấy đầy đủ thành phần giao diện phỏng vấn.');
        return;
    }

    const totalQuestions = job.questions.length;

    let recognition = null;
    let recorder = null;
    let stream = null;
    let chunks = [];

    let recording = false;
    let restarting = false;
    let analyzing = false;

    let finalText = '';
    let startedAt = 0;
    let elapsedBeforeStop = 0;
    let timer = null;

    let questionIndex = 0;
    let analyzedQuestions = new Set();

    const supportsSpeech =
        'SpeechRecognition' in window ||
        'webkitSpeechRecognition' in window;

    // Hiển thị dữ liệu dưới dạng văn bản an toàn.
    function setText(element, value) {
        element.textContent =
            value === null || value === undefined || value === ''
                ? '—'
                : String(value);
    }

    function addTextElement(parent, label, value) {
        const p = document.createElement('p');
        const b = document.createElement('b');

        b.textContent = `${label}: `;
        p.appendChild(b);

        const text = Array.isArray(value)
            ? value.join(', ')
            : value;

        p.appendChild(
            document.createTextNode(
                text === null || text === undefined || text === ''
                    ? '—'
                    : String(text)
            )
        );

        parent.appendChild(p);
    }

    function renderTranscript(interim = '') {
        transcript.value = `${finalText} ${interim}`.trim();
        transcript.scrollTop = transcript.scrollHeight;
    }

    function updateProgress() {
        const completed = analyzedQuestions.size;
        const percent = Math.round(
            (completed / totalQuestions) * 100
        );

        progress.style.width = `${percent}%`;
        progress.setAttribute('role', 'progressbar');
        progress.setAttribute('aria-valuemin', '0');
        progress.setAttribute('aria-valuemax', '100');
        progress.setAttribute('aria-valuenow', String(percent));
        progress.setAttribute(
            'aria-label',
            `Đã phân tích ${completed}/${totalQuestions} câu hỏi`
        );
    }

    function tick() {
        if (!startedAt) return;

        const seconds =
            elapsedBeforeStop +
            Math.floor((Date.now() - startedAt) / 1000);

        timerEl.textContent =
            `${String(Math.floor(seconds / 60)).padStart(2, '0')}:` +
            `${String(seconds % 60).padStart(2, '0')}`;
    }

    function resetQuestionTimer() {
        clearInterval(timer);

        startedAt = 0;
        elapsedBeforeStop = 0;

        timerEl.textContent = '00:00';
    }

    function buildRecognition() {
        if (!supportsSpeech) return null;

        const Recognition =
            window.SpeechRecognition ||
            window.webkitSpeechRecognition;

        const r = new Recognition();

        r.lang = 'vi-VN';
        r.continuous = false;
        r.interimResults = true;
        r.maxAlternatives = 1;

        r.onstart = () => {
            restarting = false;
            speechState.textContent = 'Đang nghe…';
        };

        r.onresult = (event) => {
            let interim = '';

            for (
                let i = event.resultIndex;
                i < event.results.length;
                i++
            ) {
                const phrase =
                    event.results[i][0].transcript.trim();

                if (event.results[i].isFinal) {
                    finalText =
                        `${finalText} ${phrase}`.trim();
                } else {
                    interim += `${phrase} `;
                }
            }

            renderTranscript(interim);
        };

        r.onerror = (event) => {
            if (
                event.error === 'not-allowed' ||
                event.error === 'service-not-allowed'
            ) {
                speechState.textContent =
                    'Chưa được cấp quyền microphone';

                return;
            }

            if (event.error !== 'aborted') {
                speechState.textContent =
                    'Không thể nhận dạng giọng nói';
            }
        };

        r.onend = () => {
            if (recording && !restarting) {
                restarting = true;

                setTimeout(() => {
                    if (!recording || recognition !== r) {
                        restarting = false;
                        return;
                    }

                    try {
                        r.start();
                    } catch (_) {
                        restarting = false;
                    }
                }, 150);
            } else if (!recording) {
                speechState.textContent = supportsSpeech
                    ? 'Đã dừng nhận dạng'
                    : 'Speech-to-Text không khả dụng';
            }
        };

        return r;
    }

    async function startRecording() {
        if (recording || analyzing) return;

        if (
            !navigator.mediaDevices?.getUserMedia ||
            !window.MediaRecorder
        ) {
            speechState.textContent =
                'Trình duyệt không hỗ trợ ghi âm';

            return;
        }

        try {
            stream = await navigator.mediaDevices.getUserMedia({
                audio: true
            });

            chunks = [];

            recorder = new MediaRecorder(stream);

            recorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    chunks.push(event.data);
                }
            };

            recorder.onerror = () => {
                speechState.textContent =
                    'Có lỗi khi ghi âm';
            };

            recorder.onstop = async () => {
                try {
                    if (chunks.length === 0) return;

                    const blob = new Blob(chunks, {
                        type: recorder?.mimeType || 'audio/webm'
                    });

                    const formData = new FormData();

                    formData.append(
                        'audio',
                        blob,
                        'answer.webm'
                    );

                    const response = await fetch('/api/audio', {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        speechState.textContent =
                            'Đã ghi âm nhưng tải tệp lên thất bại';
                    }
                } catch (error) {
                    console.error('Lỗi tải bản ghi:', error);

                    speechState.textContent =
                        'Không thể tải bản ghi âm lên';
                } finally {
                    if (stream) {
                        stream.getTracks().forEach(
                            (track) => track.stop()
                        );

                        stream = null;
                    }
                }
            };

            finalText = transcript.value.trim();

            recorder.start(500);

            recording = true;
            restarting = false;
            startedAt = Date.now();

            clearInterval(timer);
            timer = setInterval(tick, 250);

            recordBtn.classList.add('is-recording');
            recordBtn.innerHTML =
                '<span></span>Dừng trả lời';

            recordState.textContent = 'Đang ghi';

            recognition = buildRecognition();

            if (recognition) {
                try {
                    recognition.start();
                } catch (error) {
                    console.warn(
                        'Không thể bắt đầu Speech Recognition:',
                        error
                    );

                    speechState.textContent =
                        'Đang ghi âm, không nhận dạng được giọng nói';
                }
            } else {
                speechState.textContent =
                    'Hãy dùng Chrome hoặc Edge để nhận dạng giọng nói';
            }
        } catch (error) {
            console.error('Lỗi microphone:', error);

            if (stream) {
                stream.getTracks().forEach(
                    (track) => track.stop()
                );

                stream = null;
            }

            recording = false;

            speechState.textContent =
                'Không thể truy cập microphone. Hãy kiểm tra quyền trình duyệt.';
        }
    }

    function stopRecognition() {
        const currentRecognition = recognition;

        recognition = null;
        restarting = false;

        if (currentRecognition) {
            try {
                currentRecognition.stop();
            } catch (_) {
                // Recognition có thể đã dừng.
            }
        }
    }

    function stopRecording() {
        if (!recording) return;

        recording = false;

        if (startedAt) {
            elapsedBeforeStop += Math.floor(
                (Date.now() - startedAt) / 1000
            );
        }

        startedAt = 0;

        clearInterval(timer);
        timer = null;

        stopRecognition();

        if (recorder && recorder.state !== 'inactive') {
            recorder.stop();
        } else if (stream) {
            stream.getTracks().forEach(
                (track) => track.stop()
            );

            stream = null;
        }

        recordBtn.classList.remove('is-recording');
        recordBtn.innerHTML =
            '<span></span>Bắt đầu trả lời';

        recordState.textContent = 'Đã ghi';
        tick();
    }

    recordBtn.addEventListener('click', async () => {
        if (recording) {
            stopRecording();
        } else {
            await startRecording();
        }
    });

    // Hiển thị kết quả phân tích an toàn.
    function renderAnalysis(data) {
        setText(score, Math.round(Number(data.overall) || 0));

        criteriaResult.replaceChildren();

        Object.entries(data.criteria || {}).forEach(
            ([name, value]) => {
                const numericValue = Math.max(
                    0,
                    Math.min(100, Number(value) || 0)
                );

                const row = document.createElement('div');
                row.className = 'result-row';

                const label = document.createElement('span');
                label.textContent = name;

                const bar = document.createElement('div');
                bar.className = 'bar';

                const fill = document.createElement('i');
                fill.style.width = `${numericValue}%`;

                const number = document.createElement('b');
                number.textContent = String(
                    Math.round(numericValue)
                );

                bar.appendChild(fill);
                row.append(label, bar, number);
                criteriaResult.appendChild(row);
            }
        );

        feedback.replaceChildren();

        addTextElement(
            feedback,
            'Độ liên quan câu trả lời',
            `${Math.round(Number(data.relevance) || 0)}/100`
        );

        addTextElement(
            feedback,
            'Evidence',
            Object.entries(data.evidence || {})
                .map(([criterion, details]) => {
                    if (!details || typeof details !== 'object') {
                        return `${criterion}: ${details ?? '—'}`;
                    }

                    const keywords = Array.isArray(details.keywords)
                        ? details.keywords
                        : [];

                    const actions = Array.isArray(details.actions)
                        ? details.actions
                        : [];

                    const skills = Array.isArray(details.skills)
                        ? details.skills
                        : [];

                    const signals = [
                        ...keywords,
                        ...actions,
                        ...skills
                    ];

                    if (details.has_example) {
                        signals.push('Có ví dụ');
                    }

                    if (details.has_result) {
                        signals.push('Có kết quả');
                    }

                    if (details.has_steps) {
                        signals.push('Có trình tự thực hiện');
                    }

                    return `${criterion}: ${
                        signals.length
                            ? [...new Set(signals)].join(', ')
                            : 'Chưa phát hiện tín hiệu rõ ràng'
                    }`;
                })
                .join(' | ') || 'Chưa phát hiện tín hiệu rõ ràng.'
        );

        addTextElement(
            feedback,
            'Giải thích',
            data.explanation || '—'
        );

        addTextElement(
            feedback,
            'Đã làm tốt',
            data.strengths || 'Chưa đủ bằng chứng.'
        );

        addTextElement(
            feedback,
            'Cần cải thiện',
            data.improvements || 'Không có điểm yếu nổi bật.'
        );

        addTextElement(
            feedback,
            'Bước tiếp theo',
            data.action || '—'
        );

        addTextElement(
            feedback,
            'Transcript đã làm sạch',
            data.cleaned || '—'
        );
    }

    analyzeBtn.addEventListener('click', async () => {
        if (analyzing) return;

        if (recording) {
            stopRecording();
        }

        const answer = transcript.value.trim();

        if (!answer) {
            transcript.focus();
            speechState.textContent =
                'Hãy nhập hoặc ghi âm câu trả lời trước';

            return;
        }

        analyzing = true;

        analyzeBtn.disabled = true;
        recordBtn.disabled = true;
        analyzeBtn.textContent = 'Đang phân tích…';

        try {
            const duration = elapsedBeforeStop;

            const response = await fetch('/api/answer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    question: job.questions[questionIndex],
                    answer,
                    duration
                })
            });

            const raw = await response.text();

            let data;

            try {
                data = JSON.parse(raw);
            } catch (_) {
                throw new Error(
                    'Máy chủ chưa trả về dữ liệu phân tích hợp lệ.'
                );
            }

            if (!response.ok || data.error) {
                throw new Error(
                    data.error ||
                    'Không thể phân tích câu trả lời.'
                );
            }

            renderAnalysis(data);

            analyzedQuestions.add(questionIndex);
            updateProgress();

            nextBtn.textContent =
                questionIndex + 1 >= totalQuestions
                    ? 'Xem báo cáo'
                    : 'Câu hỏi tiếp theo';

            nextBtn.disabled = false;

            result.classList.remove('hidden');

            result.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        } catch (error) {
            console.error('Lỗi phân tích:', error);

            feedback.replaceChildren();

            const message = document.createElement('p');
            message.className = 'error-text';
            message.textContent =
                error.message || 'Đã xảy ra lỗi không xác định.';

            feedback.appendChild(message);
            result.classList.remove('hidden');
        } finally {
            analyzing = false;

            analyzeBtn.disabled = false;
            recordBtn.disabled = false;

            analyzeBtn.textContent = 'Phân tích câu trả lời';
        }
    });

    nextBtn.addEventListener('click', () => {
        // Không chuyển câu nếu chưa phân tích thành công.
        if (!analyzedQuestions.has(questionIndex)) {
            feedback.textContent =
                'Hãy phân tích câu trả lời trước khi chuyển câu hỏi.';

            result.classList.remove('hidden');
            return;
        }

        questionIndex++;

        if (questionIndex >= totalQuestions) {
            window.location.href = '/report';
            return;
        }

        qIndex.textContent = String(
            questionIndex + 1
        ).padStart(2, '0');

        questionEl.textContent =
            job.questions[questionIndex];

        transcript.value = '';
        finalText = '';

        result.classList.add('hidden');

        resetQuestionTimer();

        recordState.textContent = 'Sẵn sàng';
        speechState.textContent = 'Chưa ghi âm';

        nextBtn.disabled = false;

        updateProgress();

        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });

    // Khởi tạo giao diện.
    qIndex.textContent = '01';
    questionEl.textContent = job.questions[0];

    nextBtn.textContent =
        totalQuestions === 1
            ? 'Xem báo cáo'
            : 'Câu hỏi tiếp theo';

    updateProgress();
})();