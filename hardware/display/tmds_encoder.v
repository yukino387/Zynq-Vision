module tmds_encoder (
    input wire clk,input wire reset,input wire active,
    input wire c0,input wire c1,input wire [7:0] data,
    output reg [9:0] encoded=10'b1101010100
);
    integer ones,i,balance;
    reg [8:0] q;
    reg signed [5:0] disparity=0;
    always @* begin
        ones=0;for(i=0;i<8;i=i+1)ones=ones+data[i];
        q[8]=!(ones>4 || (ones==4 && !data[0]));q[0]=data[0];
        for(i=1;i<8;i=i+1)q[i]=q[8]?(q[i-1]^data[i]):~(q[i-1]^data[i]);
        ones=0;for(i=0;i<8;i=i+1)ones=ones+q[i];balance=2*ones-8;
    end
    always @(posedge clk) begin
        if(reset || !active) begin
            disparity<=0;
            case({c1,c0})
                2'b00:encoded<=10'b1101010100;
                2'b01:encoded<=10'b0010101011;
                2'b10:encoded<=10'b0101010100;
                2'b11:encoded<=10'b1010101011;
            endcase
        end else if(disparity==0 || balance==0) begin
            encoded<={~q[8],q[8],q[8]?q[7:0]:~q[7:0]};
            disparity<=disparity+(q[8]?balance:-balance);
        end else if((disparity>0 && balance>0)||(disparity<0 && balance<0)) begin
            encoded<={1'b1,q[8],~q[7:0]};disparity<=disparity+(q[8]?2:0)-balance;
        end else begin
            encoded<={1'b0,q[8],q[7:0]};disparity<=disparity+balance-(q[8]?0:2);
        end
    end
endmodule
