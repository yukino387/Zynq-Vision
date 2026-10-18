`timescale 1ns/1ps
module display_tb;
    reg clk=0;always #5 clk=~clk;
    reg reset=1;
    wire active,hsync,vsync,frame_start,line_end;
    wire [10:0] x;wire [9:0] y;
    video_timing timing(clk,reset,active,hsync,vsync,frame_start,line_end,x,y);
    reg enc_active=0,c0=0,c1=0;reg [7:0] data=0;wire [9:0] encoded;
    tmds_encoder encoder(clk,reset,enc_active,c0,c1,data,encoded);
    integer cycle,active_count=0,hsync_count=0,vsync_count=0,starts=0,value,bit_index,ones,balance=0,file;
    reg [7:0] q,decoded;
    initial begin
        repeat(3)@(negedge clk);reset=0;
        for(cycle=0;cycle<1650*750;cycle=cycle+1)begin
            #1;
            if(x!==cycle%1650 || y!==cycle/1650)$fatal(1,"Raster position mismatch");
            if(active)active_count=active_count+1;
            if(hsync)hsync_count=hsync_count+1;
            if(vsync)vsync_count=vsync_count+1;
            if(frame_start)starts=starts+1;
            @(posedge clk);#1;
        end
        if(active_count!=1280*720 || hsync_count!=40*750 || vsync_count!=5*1650 || starts!=1)$fatal(1,"720p timing geometry mismatch");
        for(value=0;value<4;value=value+1)begin
            c0=value&1;c1=(value>>1)&1;@(posedge clk);#1;
            case(value)
                0:if(encoded!==10'b1101010100)$fatal(1,"Control 00 mismatch");
                1:if(encoded!==10'b0010101011)$fatal(1,"Control 01 mismatch");
                2:if(encoded!==10'b0101010100)$fatal(1,"Control 10 mismatch");
                3:if(encoded!==10'b1010101011)$fatal(1,"Control 11 mismatch");
            endcase
        end
        enc_active=1;
        for(value=0;value<4096;value=value+1)begin
            data=(value*73+value/256)&255;@(posedge clk);#1;
            q=encoded[9]?~encoded[7:0]:encoded[7:0];decoded[0]=q[0];
            for(bit_index=1;bit_index<8;bit_index=bit_index+1)decoded[bit_index]=encoded[8]?(q[bit_index]^q[bit_index-1]):~(q[bit_index]^q[bit_index-1]);
            if(decoded!==data)$fatal(1,"TMDS data round-trip mismatch");
            ones=0;for(bit_index=0;bit_index<10;bit_index=bit_index+1)ones=ones+encoded[bit_index];
            balance=balance+2*ones-10;
            if(balance>8 || balance< -8)$fatal(1,"TMDS running disparity out of bounds");
        end
        file=$fopen("logic.PASS","w");$fwrite(file,"720p raster and TMDS round-trip passed\n");$fclose(file);
        $display("DISPLAY_LOGIC_PASS");$finish;
    end
endmodule
