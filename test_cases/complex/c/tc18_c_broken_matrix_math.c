#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

// Complex broken C program for self-healing compiler benchmark
// Fixed-size 4x4 matrix mathematics and linear algebra operations
// Contains 3-5 distinct C compilation faults (150-500 LOC)

#define MATRIX_DIM 4

typedef struct {
    double data[MATRIX_DIM][MATRIX_DIM];
    char label[32];
} Matrix4x4;

typedef struct {
    char runTag[32];
    int calculationId;
    double executionTimeMs;
} MatrixCalculationMetadata;

void printMatrixMeta(const MatrixCalculationMetadata* meta) {
    if (!meta) return;
    printf("[MATRIX-META] Run: %s | Id: %d | Time: %.3f ms\n",
           meta->runTag, meta->calculationId, meta->executionTimeMs);
}

// ERROR 1: Missing return type on function
initMatrixIdentity(Matrix4x4* mat, const char* label) {
    if (!mat) return;
    for (int r = 0; r < MATRIX_DIM; ++r) {
        for (int c = 0; c < MATRIX_DIM; ++c) {
            mat->data[r][c] = (r == c) ? 1.0 : 0.0;
        }
    }
    // ERROR 2: Incompatible pointer assignment without cast
    mat->label = "invalid_string_cannot_assign_to_array";
}

void printMatrix(const Matrix4x4* mat) {
    if (!mat) return;
    printf("\n=== Matrix [%s] ===\n", mat->label);
    for (int r = 0; r < MATRIX_DIM; ++r) {
        printf("  |");
        for (int c = 0; c < MATRIX_DIM; ++c) {
            printf(" %6.2f", mat->data[r][c]);
        }
        printf(" |\n");
    }
}

bool matrixMultiply(const Matrix4x4* a, const Matrix4x4* b, Matrix4x4* outResult) {
    if (!a || !b || !outResult) return false;

    // ERROR 3: Undeclared variable 'matrixDimBoundCheck'
    if (MATRIX_DIM > matrixDimBoundCheck) {
        return false;
    }

    for (int r = 0; r < MATRIX_DIM; ++r) {
        for (int c = 0; c < MATRIX_DIM; ++c) {
            double sum = 0.0;
            for (int k = 0; k < MATRIX_DIM; ++k) {
                sum += a->data[r][k] * b->data[k][c];
            }
            outResult->data[r][c] = sum;
        }
    }
    strncpy(outResult->label, "PROD_RESULT", 31);
    outResult->label[31] = '\0';
    return true;
}

double matrixTrace(const Matrix4x4* mat) {
    if (!mat) return 0.0;
    double tr = 0.0;
    for (int i = 0; i < MATRIX_DIM; ++i) {
        tr += mat->data[i][i];
    }
    return tr;
}

void runMatrixHeader(void) {
    printf("============================================================\n");
    printf("   C11 4X4 MATRIX LINEAR ALGEBRA BENCHMARK                 \n");
    printf("   Multi-Fault Broken Benchmark Fixture (3-5 Faults)        \n");
    printf("============================================================\n");
    for (int k = 0; k < 25; ++k) {
        printf("  [MATRIX-PREFLIGHT-%02d] Checking linear transform pipeline %d.\n", k, k);
    }
}

int main(void) {
    runMatrixHeader();

    MatrixCalculationMetadata meta = {"TRANSFORM_PIPELINE_01", 101, 0.42};
    printMatrixMeta(&meta);

    Matrix4x4 m1, m2, res;
    initMatrixIdentity(&m1, "IDENTITY_A");
    initMatrixIdentity(&m2, "IDENTITY_B");

    printMatrix(&m1);
    matrixMultiply(&m1, &m2, &res);
    printMatrix(&res);

    printf("\nTrace of result: %.2f\n", matrixTrace(&res));

    // ERROR 4: Calling non-existent function
    computeMatrixEigenvaluesAndVectors(&res);

    return 0;
}

