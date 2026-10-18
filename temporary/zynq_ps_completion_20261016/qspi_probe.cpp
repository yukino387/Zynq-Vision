#include "xqspips.h"
#include "xparameters.h"
#include "xil_cache.h"
#include "sleep.h"
#include <cstring>
int main(){
 Xil_DCacheDisable();auto out=reinterpret_cast<volatile unsigned*>(0x03000000);std::memset((void*)out,0,256);
 XQspiPs q;auto cfg=XQspiPs_LookupConfig(XPAR_XQSPIPS_0_BASEADDR);
 out[0]=0x50524f42;out[1]=cfg?XQspiPs_CfgInitialize(&q,cfg,cfg->BaseAddress):99;
 if(out[1])while(1){}
 XQspiPs_SetOptions(&q,XQSPIPS_MANUAL_START_OPTION|XQSPIPS_FORCE_SSELECT_OPTION|XQSPIPS_HOLD_B_DRIVE_OPTION);
 XQspiPs_SetSlaveSelect(&q);
 for(unsigned p=0;p<8;++p){
  XQspiPs_SetClkPrescaler(&q,7-p);unsigned char tx[]={0x9f,0x23,0x08,0x09},rx[4]={};
  out[2+2*p]=XQspiPs_PolledTransfer(&q,tx,rx,4);
  out[3+2*p]=(unsigned(rx[0])<<24)|(unsigned(rx[1])<<16)|(unsigned(rx[2])<<8)|rx[3];
 }
 out[18]=0x444f4e45;while(1){}
}
