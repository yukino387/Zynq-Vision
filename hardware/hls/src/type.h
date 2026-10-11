#include<ap_fixed.h>
#include<ap_int.h>

#include<iostream>// for debug
#include<stdio.h> //for debug
using namespace std; //for debug

typedef ap_fixed<16,7,AP_RND,AP_SAT> data_t;
//typedef float data_t; // for debug  float C语言原生数据类型，仿真比 ap_fixed 快很多
