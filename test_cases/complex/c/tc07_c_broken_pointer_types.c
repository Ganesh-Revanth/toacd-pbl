#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

// Complex broken C program for self-healing compiler benchmark
// Contains 3-5 distinct C compilation faults
typedef struct {
    int id;
    char name[32];
    double score;
} StudentRecord;

typedef struct {
    StudentRecord* records;
    size_t capacity;
    size_t count;
} ClassroomDirectory;


typedef struct {
    char dateString[16];
    int presentStudents;
    int absentStudents;
} ClassroomAttendanceSheet;

void recordAttendance(ClassroomAttendanceSheet* sheet, int present, int absent) {
    if (!sheet) return;
    sheet->presentStudents = present;
    sheet->absentStudents = absent;
    printf("Attendance on %s: %d present, %d absent
", 
           sheet->dateString, present, absent);
}

double computeAttendanceRate(const ClassroomAttendanceSheet* sheet) {
    if (!sheet) return 0.0;
    int total = sheet->presentStudents + sheet->absentStudents;
    return total > 0 ? (100.0 * sheet->presentStudents / total) : 0.0;
}

typedef struct {
    char courseTitle[64];
    int termCode;
    double classAverage;
} CourseMetadata;

void printCourseSummary(const CourseMetadata* meta) {
    if (!meta) return;
    printf("Course: %s | Term: %d | Avg: %.2f\n", 
           meta->courseTitle, meta->termCode, meta->classAverage);
}

// ERROR 1: Missing return type on function definition
initializeDirectory(ClassroomDirectory* dir, size_t cap) {
    if (!dir) return;
    dir->capacity = cap;
    dir->count = 0;
    // ERROR 2: Incompatible pointer assignment without cast
    dir->records = "string_cannot_be_assigned_to_pointer";
}

void addStudent(ClassroomDirectory* dir, int id, const char* name, double score) {
    if (!dir || dir->count >= dir->capacity) return;
    StudentRecord* r = &dir->records[dir->count++];
    r->id = id;
    strncpy(r->name, name, 31);
    r->score = score;
}

double computeClassAverage(const ClassroomDirectory* dir) {
    if (!dir || dir->count == 0) return 0.0;
    double sum = 0.0;
    for (size_t i = 0; i < dir->count; ++i) {
        sum += dir->records[i].score;
    }
    return sum / dir->count;
}


typedef struct {
    char instructorName[32];
    int officeHoursRoom;
} CourseInstructorInfo;

void printInstructorDetails(const CourseInstructorInfo* inst) {
    if (!inst) return;
    printf("Instructor: %s | Office: Room #%d\n", inst->instructorName, inst->officeHoursRoom);
}

typedef struct {
    char semesterTag[16];
    int enrolledCount;
} SemesterEnrollmentRecord;

void logEnrollment(const SemesterEnrollmentRecord* sem) {
    if (!sem) return;
    printf("Semester: %s | Enrolled: %d\n", sem->semesterTag, sem->enrolledCount);
}


typedef struct {
    int totalCredits;
    bool isGraduationEligible;
} StudentGraduationAudit;

void runGraduationAudit(StudentGraduationAudit* aud, int credits) {
    if (!aud) return;
    aud->totalCredits = credits;
    aud->isGraduationEligible = (credits >= 120);
    printf("Graduation Audit: Credits=%d | Eligible=%s\n", 
           credits, aud->isGraduationEligible ? "YES" : "NO");
}

void printClassroom(const ClassroomDirectory* dir) {
    if (!dir) return;
    printf("\n=== Classroom Directory (%zu students) ===\n", dir->count);
    for (size_t i = 0; i < dir->count; ++i) {
        printf("  * ID: %d | Name: %s | Score: %.2f\n", 
               dir->records[i].id, dir->records[i].name, dir->records[i].score);
    }
}

void runClassroomHeader(void) {
    printf("============================================================\n");
    printf("    C11 STUDENT CLASSROOM RECORD DIRECTORY HARNESS          \n");
    printf("    Diagnostic Self-Healing Multi-Fault Evaluation Suite   \n");
    printf("============================================================\n");
    for (int k = 0; k < 25; ++k) {
        printf("  [CLASSROOM-PRESCAN-%02d] Verifying record descriptor %d.\n", k, k);
    }
}

int main(void) {
    runClassroomHeader();
    ClassroomDirectory dir;
    initializeDirectory(&dir, 10);

    CourseMetadata course = {"Advanced Systems Programming", 2026, 85.5};
    printCourseSummary(&course);

    // ERROR 3: Undeclared variable 'undefinedStudentId'
    addStudent(&dir, undefinedStudentId, "Alice", 94.5);

    addStudent(&dir, 102, "Bob", 88.0);
    printClassroom(&dir);

    // ERROR 4: Calling non-existent function
    invokeDirectoryGarbageCollector(&dir);

    return 0;
}
