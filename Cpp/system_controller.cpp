// ============================================================
//  ELZ Assistant - System Controller (C++ Android NDK)
//  File: system_controller.cpp
//  Purpose: Low-level system operations, file I/O,
//           performance metrics and hardware bridge
// ============================================================

#include <jni.h>
#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <dirent.h>
#include <sys/stat.h>
#include <sys/sysinfo.h>
#include <unistd.h>
#include <cstring>
#include <ctime>
#include <android/log.h>

#define LOG_TAG "ELZ_SysCtrl"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// ---- Read a text file fully -----------------------------------
static std::string readFile(const std::string& path) {
    std::ifstream f(path);
    if (!f.is_open()) return "";
    std::ostringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

// ---- Write a text file ----------------------------------------
static bool writeFile(const std::string& path, const std::string& content) {
    std::ofstream f(path, std::ios::trunc);
    if (!f.is_open()) return false;
    f << content;
    return true;
}

// ---- Append a line to a log file ------------------------------
static bool appendLine(const std::string& path, const std::string& line) {
    std::ofstream f(path, std::ios::app);
    if (!f.is_open()) return false;
    f << line << "\n";
    return true;
}

// ---- List directory entries -----------------------------------
static std::vector<std::string> listDir(const std::string& dirPath) {
    std::vector<std::string> entries;
    DIR* dir = opendir(dirPath.c_str());
    if (!dir) return entries;
    struct dirent* ent;
    while ((ent = readdir(dir)) != nullptr) {
        std::string name(ent->d_name);
        if (name == "." || name == "..") continue;
        entries.push_back(name);
    }
    closedir(dir);
    return entries;
}

// ---- Get CPU usage from /proc/stat ----------------------------
static float getCpuUsage() {
    std::ifstream stat1("/proc/stat");
    std::string line1;
    std::getline(stat1, line1);

    unsigned long long user1, nice1, sys1, idle1, iow1, irq1, sirq1;
    sscanf(line1.c_str() + 5, "%llu %llu %llu %llu %llu %llu %llu",
           &user1, &nice1, &sys1, &idle1, &iow1, &irq1, &sirq1);

    usleep(200000); // 200 ms sample

    std::ifstream stat2("/proc/stat");
    std::string line2;
    std::getline(stat2, line2);

    unsigned long long user2, nice2, sys2, idle2, iow2, irq2, sirq2;
    sscanf(line2.c_str() + 5, "%llu %llu %llu %llu %llu %llu %llu",
           &user2, &nice2, &sys2, &idle2, &iow2, &irq2, &sirq2);

    unsigned long long total1 = user1 + nice1 + sys1 + idle1 + iow1 + irq1 + sirq1;
    unsigned long long total2 = user2 + nice2 + sys2 + idle2 + iow2 + irq2 + sirq2;
    unsigned long long dIdle  = idle2 - idle1;
    unsigned long long dTotal = total2 - total1;

    if (dTotal == 0) return 0.0f;
    return 100.0f * (1.0f - static_cast<float>(dIdle) / static_cast<float>(dTotal));
}

// ---- Get RAM info from sysinfo --------------------------------
static void getRamInfo(long long& totalKB, long long& freeKB) {
    struct sysinfo info;
    if (sysinfo(&info) == 0) {
        totalKB = (info.totalram * info.mem_unit) / 1024LL;
        freeKB  = (info.freeram  * info.mem_unit) / 1024LL;
    } else {
        totalKB = 0;
        freeKB  = 0;
    }
}

// ---- ISO timestamp --------------------------------------------
static std::string isoTimestamp() {
    time_t now = time(nullptr);
    struct tm* t = localtime(&now);
    char buf[32];
    strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S", t);
    return std::string(buf);
}

// ============================================================
//  JNI Exports
// ============================================================

extern "C" {

// readFileContent(String path) -> String
JNIEXPORT jstring JNICALL
Java_com_elzhots_assistant_SystemController_readFileContent(
        JNIEnv* env, jobject /*thiz*/, jstring jPath) {
    const char* path = env->GetStringUTFChars(jPath, nullptr);
    std::string content = readFile(path);
    env->ReleaseStringUTFChars(jPath, path);
    return env->NewStringUTF(content.c_str());
}

// writeFileContent(String path, String content) -> boolean
JNIEXPORT jboolean JNICALL
Java_com_elzhots_assistant_SystemController_writeFileContent(
        JNIEnv* env, jobject /*thiz*/, jstring jPath, jstring jContent) {
    const char* path    = env->GetStringUTFChars(jPath, nullptr);
    const char* content = env->GetStringUTFChars(jContent, nullptr);
    bool ok = writeFile(path, content);
    env->ReleaseStringUTFChars(jPath, path);
    env->ReleaseStringUTFChars(jContent, content);
    return ok ? JNI_TRUE : JNI_FALSE;
}

// appendToLog(String path, String line) -> boolean
JNIEXPORT jboolean JNICALL
Java_com_elzhots_assistant_SystemController_appendToLog(
        JNIEnv* env, jobject /*thiz*/, jstring jPath, jstring jLine) {
    const char* path = env->GetStringUTFChars(jPath, nullptr);
    const char* line = env->GetStringUTFChars(jLine, nullptr);
    std::string entry = isoTimestamp() + " | " + line;
    bool ok = appendLine(path, entry);
    env->ReleaseStringUTFChars(jPath, path);
    env->ReleaseStringUTFChars(jLine, line);
    return ok ? JNI_TRUE : JNI_FALSE;
}

// listDirectory(String path) -> String[]
JNIEXPORT jobjectArray JNICALL
Java_com_elzhots_assistant_SystemController_listDirectory(
        JNIEnv* env, jobject /*thiz*/, jstring jPath) {
    const char* path = env->GetStringUTFChars(jPath, nullptr);
    auto entries = listDir(path);
    env->ReleaseStringUTFChars(jPath, path);

    jclass strCls = env->FindClass("java/lang/String");
    jobjectArray arr = env->NewObjectArray(static_cast<jsize>(entries.size()), strCls, nullptr);
    for (int i = 0; i < static_cast<int>(entries.size()); ++i)
        env->SetObjectArrayElement(arr, i, env->NewStringUTF(entries[i].c_str()));
    return arr;
}

// getCpuUsagePercent() -> float
JNIEXPORT jfloat JNICALL
Java_com_elzhots_assistant_SystemController_getCpuUsagePercent(
        JNIEnv* env, jobject /*thiz*/) {
    (void)env;
    return getCpuUsage();
}

// getRamInfoKB() -> long[2]  {total, free}
JNIEXPORT jlongArray JNICALL
Java_com_elzhots_assistant_SystemController_getRamInfoKB(
        JNIEnv* env, jobject /*thiz*/) {
    long long total = 0, free = 0;
    getRamInfo(total, free);
    jlongArray arr = env->NewLongArray(2);
    jlong buf[2] = { static_cast<jlong>(total), static_cast<jlong>(free) };
    env->SetLongArrayRegion(arr, 0, 2, buf);
    return arr;
}

// getTimestamp() -> String
JNIEXPORT jstring JNICALL
Java_com_elzhots_assistant_SystemController_getTimestamp(
        JNIEnv* env, jobject /*thiz*/) {
    return env->NewStringUTF(isoTimestamp().c_str());
}

// fileExists(String path) -> boolean
JNIEXPORT jboolean JNICALL
Java_com_elzhots_assistant_SystemController_fileExists(
        JNIEnv* env, jobject /*thiz*/, jstring jPath) {
    const char* path = env->GetStringUTFChars(jPath, nullptr);
    struct stat st{};
    bool exists = (stat(path, &st) == 0);
    env->ReleaseStringUTFChars(jPath, path);
    return exists ? JNI_TRUE : JNI_FALSE;
}

// deleteFile(String path) -> boolean
JNIEXPORT jboolean JNICALL
Java_com_elzhots_assistant_SystemController_deleteFile(
        JNIEnv* env, jobject /*thiz*/, jstring jPath) {
    const char* path = env->GetStringUTFChars(jPath, nullptr);
    bool ok = (remove(path) == 0);
    env->ReleaseStringUTFChars(jPath, path);
    return ok ? JNI_TRUE : JNI_FALSE;
}

} // extern "C"
