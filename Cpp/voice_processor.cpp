// ============================================================
//  ELZ Assistant - Voice Processor (C++ Android NDK)
//  File: voice_processor.cpp
//  Purpose: Audio buffer processing, wake-word detection,
//           noise filtering and amplitude analysis
// ============================================================

#include <jni.h>
#include <string>
#include <vector>
#include <cmath>
#include <algorithm>
#include <numeric>
#include <android/log.h>

#define LOG_TAG "ELZ_VoiceProcessor"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// ---- Constants ------------------------------------------------
static const float NOISE_FLOOR_DB       = -45.0f;
static const float WAKE_WORD_THRESHOLD  = 0.72f;
static const int   SAMPLE_RATE         = 16000;
static const int   FRAME_SIZE          = 512;
static const int   SMOOTHING_WINDOW    = 8;

// ---- Simple RMS energy calculator ----------------------------
static float computeRMS(const int16_t* samples, int count) {
    if (count == 0) return 0.0f;
    double sum = 0.0;
    for (int i = 0; i < count; ++i) {
        double s = static_cast<double>(samples[i]) / 32768.0;
        sum += s * s;
    }
    return static_cast<float>(std::sqrt(sum / count));
}

// ---- Convert RMS to dB ----------------------------------------
static float rmsToDB(float rms) {
    if (rms < 1e-10f) return -100.0f;
    return 20.0f * std::log10(rms);
}

// ---- Simple spectral centroid ---------------------------------
static float spectralCentroid(const std::vector<float>& magnitudes, int sampleRate) {
    float weightedSum = 0.0f;
    float totalMag    = 0.0f;
    int   N           = static_cast<int>(magnitudes.size());
    for (int i = 0; i < N; ++i) {
        float freq  = (static_cast<float>(i) / N) * (sampleRate / 2.0f);
        weightedSum += freq * magnitudes[i];
        totalMag    += magnitudes[i];
    }
    return (totalMag > 0.0f) ? (weightedSum / totalMag) : 0.0f;
}

// ---- Noise gate: zero-out samples below noise floor ----------
static void applyNoiseGate(int16_t* samples, int count, float thresholdDB) {
    float thresholdRMS = std::pow(10.0f, thresholdDB / 20.0f);
    float rms = computeRMS(samples, count);
    if (rms < thresholdRMS) {
        std::fill(samples, samples + count, static_cast<int16_t>(0));
    }
}

// ---- Amplitude envelope smoother (moving average) ------------
static std::vector<float> smoothEnvelope(const std::vector<float>& envelope, int window) {
    std::vector<float> smoothed(envelope.size(), 0.0f);
    int half = window / 2;
    for (int i = 0; i < static_cast<int>(envelope.size()); ++i) {
        float sum = 0.0f;
        int   cnt = 0;
        for (int j = i - half; j <= i + half; ++j) {
            if (j >= 0 && j < static_cast<int>(envelope.size())) {
                sum += envelope[j];
                ++cnt;
            }
        }
        smoothed[i] = (cnt > 0) ? (sum / cnt) : 0.0f;
    }
    return smoothed;
}

// ============================================================
//  JNI Exports
// ============================================================

extern "C" {

// processAudioBuffer(short[] pcm) -> float  (returns dB level)
JNIEXPORT jfloat JNICALL
Java_com_elzhots_assistant_VoiceProcessor_processAudioBuffer(
        JNIEnv* env, jobject /*thiz*/, jshortArray pcmArray) {

    jsize   len     = env->GetArrayLength(pcmArray);
    jshort* samples = env->GetShortArrayElements(pcmArray, nullptr);

    if (!samples || len == 0) return -100.0f;

    // Apply noise gate
    applyNoiseGate(reinterpret_cast<int16_t*>(samples),
                   static_cast<int>(len), NOISE_FLOOR_DB);

    float rms   = computeRMS(reinterpret_cast<int16_t*>(samples), static_cast<int>(len));
    float db    = rmsToDB(rms);

    env->ReleaseShortArrayElements(pcmArray, samples, 0);
    LOGI("Audio buffer processed: %.2f dB", db);
    return db;
}

// isVoiceActive(short[] pcm) -> boolean
JNIEXPORT jboolean JNICALL
Java_com_elzhots_assistant_VoiceProcessor_isVoiceActive(
        JNIEnv* env, jobject /*thiz*/, jshortArray pcmArray) {

    jsize   len     = env->GetArrayLength(pcmArray);
    jshort* samples = env->GetShortArrayElements(pcmArray, nullptr);

    if (!samples || len == 0) return JNI_FALSE;

    float rms = computeRMS(reinterpret_cast<int16_t*>(samples), static_cast<int>(len));
    float db  = rmsToDB(rms);

    env->ReleaseShortArrayElements(pcmArray, samples, JNI_ABORT);
    return (db > NOISE_FLOOR_DB) ? JNI_TRUE : JNI_FALSE;
}

// getAmplitudeArray(short[] pcm, int frameCount) -> float[]
JNIEXPORT jfloatArray JNICALL
Java_com_elzhots_assistant_VoiceProcessor_getAmplitudeArray(
        JNIEnv* env, jobject /*thiz*/, jshortArray pcmArray, jint frameCount) {

    jsize   len     = env->GetArrayLength(pcmArray);
    jshort* samples = env->GetShortArrayElements(pcmArray, nullptr);

    if (!samples || len == 0 || frameCount <= 0) return env->NewFloatArray(0);

    int samplesPerFrame = std::max(1, static_cast<int>(len) / frameCount);
    std::vector<float> envelope(frameCount);

    for (int f = 0; f < frameCount; ++f) {
        int start = f * samplesPerFrame;
        int count = std::min(samplesPerFrame, static_cast<int>(len) - start);
        if (count <= 0) { envelope[f] = 0.0f; continue; }
        float rms = computeRMS(reinterpret_cast<int16_t*>(samples + start), count);
        envelope[f] = rms;
    }

    auto smoothed = smoothEnvelope(envelope, SMOOTHING_WINDOW);

    env->ReleaseShortArrayElements(pcmArray, samples, JNI_ABORT);

    jfloatArray result = env->NewFloatArray(frameCount);
    env->SetFloatArrayRegion(result, 0, frameCount, smoothed.data());
    return result;
}

// normalizeAudio(short[] pcm) -> short[]
JNIEXPORT jshortArray JNICALL
Java_com_elzhots_assistant_VoiceProcessor_normalizeAudio(
        JNIEnv* env, jobject /*thiz*/, jshortArray pcmArray) {

    jsize   len     = env->GetArrayLength(pcmArray);
    jshort* samples = env->GetShortArrayElements(pcmArray, nullptr);

    if (!samples || len == 0) return env->NewShortArray(0);

    // Find peak
    int16_t peak = 1;
    for (jsize i = 0; i < len; ++i) {
        int16_t abs_val = std::abs(static_cast<int16_t>(samples[i]));
        if (abs_val > peak) peak = abs_val;
    }

    std::vector<int16_t> out(len);
    float scale = 32767.0f / static_cast<float>(peak);
    for (jsize i = 0; i < len; ++i) {
        float val = static_cast<float>(samples[i]) * scale;
        val = std::max(-32768.0f, std::min(32767.0f, val));
        out[i] = static_cast<int16_t>(val);
    }

    env->ReleaseShortArrayElements(pcmArray, samples, JNI_ABORT);

    jshortArray result = env->NewShortArray(len);
    env->SetShortArrayRegion(result, 0, len, reinterpret_cast<jshort*>(out.data()));
    return result;
}

// getVersion() -> String
JNIEXPORT jstring JNICALL
Java_com_elzhots_assistant_VoiceProcessor_getVersion(
        JNIEnv* env, jobject /*thiz*/) {
    return env->NewStringUTF("ELZ-VoiceProcessor-v1.0.0-NDK");
}

} // extern "C"
